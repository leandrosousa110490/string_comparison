from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QTextEdit)
from PyQt5.QtGui import QTextCharFormat, QColor, QSyntaxHighlighter, QFont
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QDateTime
from difflib import SequenceMatcher
import sys

class DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, other_text="", is_left=True):
        super().__init__(parent)
        self.other_text = other_text
        self.enabled = True
        self.is_left = is_left
        
        # Create formats for different types of differences
        self.deletion_format = QTextCharFormat()
        self.deletion_format.setBackground(QColor("#ffebee"))  # Light red
        self.deletion_format.setForeground(QColor("#d32f2f"))  # Dark red
        
        self.insertion_format = QTextCharFormat()
        self.insertion_format.setBackground(QColor("#e8f5e9"))  # Light green
        self.insertion_format.setForeground(QColor("#2e7d32"))  # Dark green
        
        self.modification_format = QTextCharFormat()
        self.modification_format.setBackground(QColor("#fff3e0"))  # Light orange
        self.modification_format.setForeground(QColor("#ef6c00"))  # Dark orange

    def set_other_text(self, text):
        if self.enabled:
            self.other_text = text
            self.rehighlight()

    def highlightBlock(self, text):
        if not self.enabled or not text or not self.other_text:
            return

        matcher = SequenceMatcher(None, text, self.other_text)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'delete':
                # Show deletions in red with strikethrough
                fmt = self.deletion_format
                if self.is_left:
                    fmt.setFontStrikeOut(True)
                self.setFormat(i1, i2 - i1, fmt)
            elif tag == 'insert':
                # Show insertions in green with underline
                fmt = self.insertion_format
                if not self.is_left:
                    fmt.setFontUnderline(True)
                self.setFormat(i1, i2 - i1, fmt)
            elif tag == 'replace':
                # Show modifications in orange
                self.setFormat(i1, i2 - i1, self.modification_format)

class ComparisonWorker(QThread):
    """Worker thread for handling text comparison"""
    finished = pyqtSignal(list, int)
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, text1, text2, max_diff=500, chunk_size=1000):  # Reduced limits
        super().__init__()
        # Safely truncate input texts
        self.text1 = text1[:500000] if text1 else ""  # Limit to 500KB
        self.text2 = text2[:500000] if text2 else ""
        self.max_diff = max_diff
        self.chunk_size = chunk_size
        self._is_running = True
        self._error_occurred = False
    
    def stop(self):
        self._is_running = False
    
    def run(self):
        if not self._is_running or self._error_occurred:
            return
            
        try:
            diff_content = []
            diff_count = 0
            
            # Use quick_ratio first to check similarity
            matcher = SequenceMatcher(None, self.text1, self.text2, autojunk=False)
            if matcher.quick_ratio() < 0.1:  # Texts are very different
                self.error.emit("Texts are too different for detailed comparison")
                return
            
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if not self._is_running or self._error_occurred:
                    return
                
                if tag != 'equal':
                    diff_count += 1
                    if diff_count > self.max_diff:
                        diff_content.append("... (too many differences to display)")
                        break
                    
                    try:
                        if i2 - i1 > self.chunk_size or j2 - j1 > self.chunk_size:
                            diff_content.append(f"... (difference at position {i1} too large to display)")
                            continue
                            
                        if tag == 'delete':
                            text = self.text1[i1:i2][:100]
                            diff_content.append(f'Deleted: "{text}"' + ("..." if len(text) == 100 else ""))
                        elif tag == 'insert':
                            text = self.text2[j1:j2][:100]
                            diff_content.append(f'Inserted: "{text}"' + ("..." if len(text) == 100 else ""))
                        elif tag == 'replace':
                            text1 = self.text1[i1:i2][:50]
                            text2 = self.text2[j1:j2][:50]
                            diff_content.append(f'Changed: "{text1}" → "{text2}"' + 
                                             ("..." if len(text1) == 50 or len(text2) == 50 else ""))
                    except Exception as e:
                        print(f"Error processing diff chunk: {e}")
                        continue
                
                if diff_count % 10 == 0:  # Reduced progress updates
                    self.progress.emit(diff_count)
            
            if self._is_running and not self._error_occurred:
                self.finished.emit(diff_content, diff_count)
                
        except MemoryError:
            self._error_occurred = True
            self.error.emit("Out of memory - text too large to compare")
        except Exception as e:
            self._error_occurred = True
            self.error.emit(f"Comparison error: {str(e)}")

class StringComparisonApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced String Comparison Tool")
        self.setMinimumSize(800, 600)
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Add legend
        legend_layout = QHBoxLayout()
        legend_items = [
            ("Deletions", "#ffebee", "#d32f2f"),
            ("Insertions", "#e8f5e9", "#2e7d32"),
            ("Modifications", "#fff3e0", "#ef6c00")
        ]
        
        for text, bg_color, fg_color in legend_items:
            legend_label = QLabel(f" {text} ")
            legend_label.setStyleSheet(f"""
                background-color: {bg_color};
                color: {fg_color};
                border: 1px solid {fg_color};
                border-radius: 3px;
                padding: 2px 5px;
            """)
            legend_layout.addWidget(legend_label)
        
        legend_layout.addStretch()
        layout.addLayout(legend_layout)
        
        # Create horizontal layout for text editors
        editors_layout = QHBoxLayout()
        
        # Left side (First string)
        left_layout = QVBoxLayout()
        self.left_label = QLabel("Original Text")
        self.left_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.text1 = self.create_text_edit()
        self.text1.textChanged.connect(self.schedule_update)
        self.word_count1 = QLabel("Words: 0  Characters: 0")
        
        left_layout.addWidget(self.left_label)
        left_layout.addWidget(self.text1)
        left_layout.addWidget(self.word_count1)
        
        # Right side (Second string)
        right_layout = QVBoxLayout()
        self.right_label = QLabel("Modified Text")
        self.right_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.text2 = self.create_text_edit()
        self.text2.textChanged.connect(self.schedule_update)
        self.word_count2 = QLabel("Words: 0  Characters: 0")
        
        right_layout.addWidget(self.right_label)
        right_layout.addWidget(self.text2)
        right_layout.addWidget(self.word_count2)
        
        # Add both sides to editors layout
        editors_layout.addLayout(left_layout)
        editors_layout.addLayout(right_layout)
        
        # Create highlighters
        self.highlighter1 = DiffHighlighter(self.text1.document(), is_left=True)
        self.highlighter2 = DiffHighlighter(self.text2.document(), is_left=False)
        
        # Add editors layout to main layout
        layout.addLayout(editors_layout)
        
        # Create detailed diff view
        self.diff_view = self.create_text_edit(font_size=10)
        self.diff_view.setReadOnly(True)
        self.diff_view.setMaximumHeight(150)
        self.diff_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.diff_view.setLineWrapMode(QTextEdit.NoWrap)  # Prevent line wrapping
        layout.addWidget(QLabel("Detailed Changes:"))
        layout.addWidget(self.diff_view)
        
        # Create status area
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("padding: 10px; border-radius: 5px; background-color: #e3f2fd;")
        layout.addWidget(self.status_label)
        
        # Create update timer
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.update_comparison)
        
        # Add after other initialization code
        self.comparison_worker = None
        self.update_pending = False
        self.max_text_size = 500000  # Reduced to 500KB
        self.last_comparison_time = 0
        self.comparison_cooldown = 1000  # 1 second cooldown
        
        # Style the window
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTextEdit {
                border: 1px solid #bdbdbd;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
                font-family: Consolas, Monaco, monospace !important;
                font-size: 11px !important;
                line-height: 1.4;
            }
            QLabel {
                color: #424242;
            }
        """)

    def schedule_update(self):
        """Schedule an update with debouncing"""
        if not self.update_timer.isActive():
            self.update_timer.start(500)  # Increased delay for better performance
        self.update_pending = True

    def standardize_text(self, text):
        """Standardize text formatting regardless of input source"""
        # Remove any special Unicode whitespace characters
        text = ' '.join(text.split())
        return text

    def update_comparison(self):
        if not self.update_pending:
            return
            
        current_time = QDateTime.currentMSecsSinceEpoch()
        if current_time - self.last_comparison_time < self.comparison_cooldown:
            # Reschedule update
            self.update_timer.start(self.comparison_cooldown)
            return
            
        self.update_pending = False
        self.last_comparison_time = current_time
        
        try:
            # Get text content with size limits
            text1 = self.text1.toPlainText()[:self.max_text_size]
            text2 = self.text2.toPlainText()[:self.max_text_size]
            
            # Basic validation
            if len(text1) == 0 and len(text2) == 0:
                self.status_label.setText("Enter text to compare")
                return
                
            if len(text1) >= self.max_text_size or len(text2) >= self.max_text_size:
                self.status_label.setText("⚠ Text truncated - too large for full comparison")
                self.status_label.setStyleSheet(
                    "padding: 10px; border-radius: 5px; background-color: #fff3cd;"
                )
            
            # Safely stop previous worker
            self.stop_current_worker()
            
            # Create new worker with reduced limits
            self.comparison_worker = ComparisonWorker(
                text1, 
                text2, 
                max_diff=500,
                chunk_size=1000
            )
            
            # Connect signals with proper cleanup
            self.connect_worker_signals()
            
            # Start comparison
            self.comparison_worker.start()
            
            # Update word counts and highlighters only for smaller texts
            if len(text1) < 100000 and len(text2) < 100000:
                self.update_word_counts(text1, text2)
                self.update_highlighters(text1, text2)
            
        except Exception as e:
            print(f"Error in update_comparison: {e}")
            self.handle_comparison_error(str(e))
    
    def stop_current_worker(self):
        """Safely stop the current worker thread"""
        if self.comparison_worker and self.comparison_worker.isRunning():
            try:
                self.comparison_worker.stop()
                self.comparison_worker.wait(500)
                if self.comparison_worker.isRunning():
                    self.comparison_worker.terminate()
                    self.comparison_worker.wait()
            except Exception as e:
                print(f"Error stopping worker: {e}")
    
    def connect_worker_signals(self):
        """Connect worker signals with proper cleanup"""
        try:
            # Disconnect any existing connections
            if self.comparison_worker:
                try:
                    self.comparison_worker.finished.disconnect()
                    self.comparison_worker.error.disconnect()
                    self.comparison_worker.progress.disconnect()
                except Exception:
                    pass  # Ignore disconnection errors
                
            # Connect new signals
            self.comparison_worker.finished.connect(
                lambda diff_content, diff_count: self.update_diff_view(
                    diff_content, diff_count, self.text1.toPlainText(), self.text2.toPlainText()
                )
            )
            self.comparison_worker.error.connect(self.handle_comparison_error)
            self.comparison_worker.progress.connect(self.update_progress)
        except Exception as e:
            print(f"Error connecting signals: {e}")

    def handle_comparison_error(self, error_message):
        """Handle comparison errors gracefully"""
        self.status_label.setText(f"⚠ {error_message}")
        self.status_label.setStyleSheet(
            "padding: 10px; border-radius: 5px; background-color: #ffcdd2;"
        )
        
    def update_progress(self, count):
        """Update the status with progress information"""
        if count % 100 == 0:  # Update every 100 differences
            self.status_label.setText(f"Processing... (Found {count} differences)")

    def update_diff_view(self, diff_content, diff_count, text1, text2):
        """Update the diff view with the comparison results"""
        try:
            self.diff_view.clear()
            for line in diff_content:
                self.diff_view.append(line)
            
            # Update status
            if not text1 and not text2:
                self.status_label.setText("Enter text to compare")
                self.status_label.setStyleSheet("padding: 10px; border-radius: 5px; background-color: #e3f2fd;")
            elif text1 == text2:
                self.status_label.setText("✓ Texts are identical")
                self.status_label.setStyleSheet("padding: 10px; border-radius: 5px; background-color: #c8e6c9;")
            else:
                self.status_label.setText(f"⚠ Texts are different (Found {diff_count} differences)")
                self.status_label.setStyleSheet("padding: 10px; border-radius: 5px; background-color: #ffcdd2;")
                
        except Exception as e:
            print(f"Error in update_diff_view: {e}")

    def create_text_edit(self, font_size=11):
        """Create a QTextEdit with proper scroll behavior"""
        text_edit = QTextEdit()
        text_edit.setFont(QFont("Consolas", font_size))
        text_edit.setAcceptRichText(False)
        
        # Get the vertical scrollbar
        scrollbar = text_edit.verticalScrollBar()
        
        # Store the current cursor position and selection
        last_cursor_pos = 0
        last_anchor_pos = 0
        
        def store_cursor_pos():
            nonlocal last_cursor_pos, last_anchor_pos
            cursor = text_edit.textCursor()
            last_cursor_pos = cursor.position()
            last_anchor_pos = cursor.anchor()
        
        # Prevent automatic scrolling by maintaining scroll position and cursor
        def maintain_scroll(value):
            if not text_edit.hasFocus():
                scrollbar.setValue(value)
                # Restore cursor position and selection
                cursor = text_edit.textCursor()
                text_length = len(text_edit.toPlainText())
                
                # Ensure positions are within valid range
                pos = min(last_cursor_pos, text_length)
                anchor = min(last_anchor_pos, text_length)
                
                cursor.setPosition(anchor)
                cursor.setPosition(pos, cursor.KeepAnchor)
                text_edit.setTextCursor(cursor)
        
        # Connect signals
        scrollbar.valueChanged.connect(maintain_scroll)
        text_edit.cursorPositionChanged.connect(store_cursor_pos)
        
        return text_edit

    def update_word_counts(self, text1, text2):
        """Update word counts in the UI"""
        try:
            words1 = len(text1.split()) if text1.strip() else 0
            chars1 = len(text1)
            words2 = len(text2.split()) if text2.strip() else 0
            chars2 = len(text2)
            
            self.word_count1.setText(f"Words: {words1}  Characters: {chars1}")
            self.word_count2.setText(f"Words: {words2}  Characters: {chars2}")
        except Exception as e:
            print(f"Error updating word counts: {e}")

    def update_highlighters(self, text1, text2):
        """Update highlighters in the UI"""
        try:
            self.highlighter1.enabled = len(text1) < self.max_text_size
            self.highlighter2.enabled = len(text2) < self.max_text_size
            if self.highlighter1.enabled and self.highlighter2.enabled:
                self.highlighter1.set_other_text(text2)
                self.highlighter2.set_other_text(text1)
        except Exception as e:
            print(f"Error updating highlighters: {e}")

def main():
    app = QApplication(sys.argv)
    window = StringComparisonApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
