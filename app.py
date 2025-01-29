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
    
    def __init__(self, text1, text2, max_diff=1000, chunk_size=1000):
        super().__init__()
        # Store original texts without truncation for accurate comparison
        try:
            # Convert texts to strings and limit size
            self.text1 = str(text1)[:5000000] if text1 else ""
            self.text2 = str(text2)[:5000000] if text2 else ""
        except Exception:
            self.text1 = ""
            self.text2 = ""
            
        self.max_diff = min(max_diff, 1000)  # Limit max differences
        self.chunk_size = min(chunk_size, 1000)  # Limit chunk size
        self._is_running = True
        self._error_occurred = False
        self.max_text_length = 5000000  # 5MB limit for safety
        self.max_display_diffs = 100  # Reduced maximum differences to display
        self.batch_size = 25  # Reduced batch size for better stability
    
    def stop(self):
        self._is_running = False
    
    def safe_text_slice(self, text, start, end):
        """Safely get a slice of text with error handling"""
        try:
            if not text or start >= len(text):
                return ""
            return text[max(0, start):min(len(text), end)]
        except Exception:
            return ""
    
    def run(self):
        if not self._is_running:
            return

        try:
            # Basic validation
            if not self.text1 and not self.text2:
                self.error.emit("No text to compare")
                return
                
            diff_content = []
            diff_count = 0
            total_diffs = 0
            batch_content = []
            
            try:
                # Create matcher with better accuracy settings
                matcher = SequenceMatcher(
                    isjunk=None,  # Don't consider any characters as junk for better accuracy
                    a=self.text1,
                    b=self.text2,
                    autojunk=False  # Disable autojunk for better accuracy
                )
                
                # First, get an overview of similarity
                try:
                    similarity = matcher.real_quick_ratio()
                except Exception:
                    similarity = 0
                    
                if similarity < 0.01:
                    try:
                        detailed_ratio = matcher.ratio()
                    except Exception:
                        detailed_ratio = 0
                        
                    if detailed_ratio < 0.01:
                        self.error.emit("Texts are too different for detailed comparison")
                        return

                try:
                    # Get all opcodes first to know total number of differences
                    opcodes = list(matcher.get_opcodes())
                    total_diffs = sum(1 for tag, _, _, _, _ in opcodes if tag != 'equal')
                except Exception as e:
                    self.error.emit(f"Error analyzing differences: {str(e)}")
                    return

                if total_diffs > self.max_display_diffs:
                    diff_content.append(f"⚠ Found {total_diffs} differences. Showing first {self.max_display_diffs} for performance.")
                    diff_content.append("=" * 50)
                
                # Process differences with context
                for tag, i1, i2, j1, j2 in opcodes:
                    if not self._is_running:
                        return
                        
                    if tag != 'equal':
                        diff_count += 1
                        if diff_count > self.max_display_diffs:
                            remaining = total_diffs - self.max_display_diffs
                            if remaining > 0:
                                diff_content.append(f"\n... {remaining} more differences not shown for performance reasons ...")
                            break
                        
                        try:
                            # Get more context around the change (safely)
                            context_before = self.safe_text_slice(self.text1, max(0, i1-30), i1)
                            context_after = self.safe_text_slice(self.text1, i2, min(len(self.text1), i2+30))
                            
                            if tag == 'delete':
                                deleted_text = self.safe_text_slice(self.text1, i1, i2)
                                if len(deleted_text) > 100:
                                    deleted_text = f"{deleted_text[:97]}..."
                                batch_content.append(
                                    f'Missing in second text: "{deleted_text}"\n'
                                    f'Context: "...{context_before}[MISSING]{context_after}..."'
                                )
                                
                            elif tag == 'insert':
                                inserted_text = self.safe_text_slice(self.text2, j1, j2)
                                if len(inserted_text) > 100:
                                    inserted_text = f"{inserted_text[:97]}..."
                                batch_content.append(
                                    f'Added in second text: "{inserted_text}"\n'
                                    f'Position: after "{context_before}"'
                                )
                                
                            elif tag == 'replace':
                                text1 = self.safe_text_slice(self.text1, i1, i2)
                                text2 = self.safe_text_slice(self.text2, j1, j2)
                                if len(text1) > 50: text1 = f"{text1[:47]}..."
                                if len(text2) > 50: text2 = f"{text2[:47]}..."
                                batch_content.append(
                                    f'Text changed:\n'
                                    f'Original: "{text1}"\n'
                                    f'Modified: "{text2}"\n'
                                    f'Context: "...{context_before}[CHANGED]{context_after}..."'
                                )

                            # Process in batches to prevent memory issues
                            if len(batch_content) >= self.batch_size:
                                diff_content.extend(batch_content)
                                batch_content = []
                                
                        except Exception as e:
                            print(f"Error processing diff chunk: {e}")
                            continue
                    
                    # Emit progress less frequently to reduce overhead
                    if diff_count % 50 == 0 and self._is_running:
                        self.progress.emit(diff_count)
                
                # Add any remaining batch content
                if batch_content and self._is_running:
                    diff_content.extend(batch_content)
                
                # Add detailed summary at the end
                if total_diffs > 0 and self._is_running:
                    try:
                        total_chars1 = len(self.text1)
                        total_chars2 = len(self.text2)
                        char_diff = abs(total_chars1 - total_chars2)
                        
                        # Calculate more accurate similarity
                        final_similarity = matcher.ratio() * 100
                        
                        # Calculate word-based differences (safely)
                        try:
                            words1 = set(self.text1.split())
                            words2 = set(self.text2.split())
                            unique_words1 = words1 - words2
                            unique_words2 = words2 - words1
                        except Exception:
                            unique_words1 = set()
                            unique_words2 = set()
                        
                        summary = [
                            "",
                            "=== Detailed Summary ===",
                            f"Total differences found: {total_diffs}",
                            f"Differences shown: {min(diff_count, self.max_display_diffs)}",
                            f"Character difference: {char_diff} ({'more' if total_chars2 > total_chars1 else 'fewer'} in second text)",
                            f"Overall similarity: {final_similarity:.2f}%",
                            f"Unique words in first text: {len(unique_words1)}",
                            f"Unique words in second text: {len(unique_words2)}"
                        ]
                        diff_content.extend(summary)
                    except Exception as e:
                        print(f"Error creating summary: {e}")
                
                if self._is_running and not self._error_occurred:
                    self.finished.emit(diff_content, total_diffs)
                    
            except MemoryError:
                self._error_occurred = True
                self.error.emit("Out of memory - text too large to compare")
            except Exception as e:
                self._error_occurred = True
                self.error.emit(f"Comparison error: {str(e)}")
                
        except Exception as e:
            self._error_occurred = True
            self.error.emit(f"Fatal error during comparison: {str(e)}")
        
    def __del__(self):
        """Cleanup when the worker is destroyed"""
        try:
            self.stop()
            self.wait()
        except Exception:
            pass

class StringComparisonApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced String Comparison Tool")
        self.setMinimumSize(800, 600)
        
        # Initialize state variables
        self.comparison_worker = None
        self.update_pending = False
        self.max_text_size = 1000000  # 1MB limit for highlighting
        self.last_comparison_time = 0
        self.comparison_cooldown = 1500  # 1.5 second cooldown
        self.is_processing = False
        
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
        """Schedule an update with debouncing and safety checks"""
        if self.is_processing:
            return
            
        if not self.update_timer.isActive():
            self.update_timer.start(750)  # Increased delay for better performance
        self.update_pending = True

    def standardize_text(self, text):
        """Standardize text formatting regardless of input source"""
        # Remove any special Unicode whitespace characters
        text = ' '.join(text.split())
        return text

    def update_comparison(self):
        if not self.update_pending or self.is_processing:
            return
            
        current_time = QDateTime.currentMSecsSinceEpoch()
        if current_time - self.last_comparison_time < self.comparison_cooldown:
            # Reschedule update
            self.update_timer.start(self.comparison_cooldown)
            return
            
        self.update_pending = False
        self.last_comparison_time = current_time
        self.is_processing = True
        
        try:
            # Get text content
            text1 = self.text1.toPlainText()
            text2 = self.text2.toPlainText()
            
            # Basic validation
            if len(text1) == 0 and len(text2) == 0:
                self.status_label.setText("Enter text to compare")
                self.is_processing = False
                return
            
            # Update UI for processing state
            self.status_label.setText("Processing comparison...")
            self.status_label.setStyleSheet(
                "padding: 10px; border-radius: 5px; background-color: #e3f2fd;"
            )
            
            # Safely stop previous worker
            self.stop_current_worker()
            
            # Create new worker
            self.comparison_worker = ComparisonWorker(
                text1, 
                text2, 
                max_diff=1000,
                chunk_size=1000
            )
            
            # Connect signals with proper cleanup
            self.connect_worker_signals()
            
            # Start comparison
            self.comparison_worker.start()
            
            # Update word counts and highlighters only for smaller texts
            if len(text1) < self.max_text_size and len(text2) < self.max_text_size:
                self.update_word_counts(text1, text2)
                self.update_highlighters(text1, text2)
            else:
                # Disable highlighting for large texts
                self.highlighter1.enabled = False
                self.highlighter2.enabled = False
                self.status_label.setText("⚠ Text too large for real-time highlighting")
            
        except Exception as e:
            self.handle_comparison_error(str(e))
        finally:
            self.is_processing = False
    
    def stop_current_worker(self):
        """Safely stop the current worker thread"""
        if self.comparison_worker and self.comparison_worker.isRunning():
            try:
                self.comparison_worker.stop()
                self.comparison_worker.wait(1000)  # Wait longer for cleanup
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
        self.is_processing = False
        self.status_label.setText(f"⚠ {error_message}")
        self.status_label.setStyleSheet(
            "padding: 10px; border-radius: 5px; background-color: #ffcdd2;"
        )
        
        # Clear the diff view
        self.diff_view.clear()
        self.diff_view.append("An error occurred during comparison. Please try again with shorter text or wait a moment.")
        
    def update_progress(self, count):
        """Update the status with progress information"""
        if count % 100 == 0:  # Update every 100 differences
            self.status_label.setText(f"Processing... (Found {count} differences)")

    def update_diff_view(self, diff_content, diff_count, text1, text2):
        """Update the diff view with the comparison results"""
        try:
            # Ensure we're not processing another update
            if self.is_processing:
                return
                
            self.is_processing = True
            
            # Clear the view first
            self.diff_view.clear()
            
            try:
                # Add a header with basic stats
                total_chars1 = len(text1) if text1 else 0
                total_chars2 = len(text2) if text2 else 0
                self.diff_view.append(f"Text 1 length: {total_chars1:,} characters")
                self.diff_view.append(f"Text 2 length: {total_chars2:,} characters")
                self.diff_view.append("=" * 50 + "\n")
            except Exception as e:
                print(f"Error adding header: {e}")
            
            try:
                # Set plain text for better performance with large content
                self.diff_view.setPlainText("")
                
                # Join text in chunks to prevent memory issues
                chunk_size = 1000
                combined_text = ""
                
                for i in range(0, len(diff_content), chunk_size):
                    chunk = diff_content[i:i + chunk_size]
                    combined_text += "\n".join(chunk) + "\n"
                    
                    if len(combined_text) > 1000000:  # Limit total text size
                        combined_text += "\n... Text truncated for performance ..."
                        break
                
                # Use insertPlainText for better performance
                cursor = self.diff_view.textCursor()
                cursor.movePosition(cursor.End)
                cursor.insertText(combined_text)
                
                # Move cursor to start for better visibility
                cursor.movePosition(cursor.Start)
                self.diff_view.setTextCursor(cursor)
            except Exception as e:
                print(f"Error setting diff content: {e}")
                self.diff_view.append("Error displaying full comparison results")
            
            try:
                # Update status with appropriate styling
                if not text1 and not text2:
                    self.status_label.setText("Enter text to compare")
                    self.status_label.setStyleSheet(
                        "padding: 10px; border-radius: 5px; background-color: #e3f2fd;"
                    )
                elif text1 == text2:
                    self.status_label.setText("✓ Texts are identical")
                    self.status_label.setStyleSheet(
                        "padding: 10px; border-radius: 5px; background-color: #c8e6c9;"
                    )
                else:
                    status_text = f"⚠ Found {diff_count:,} differences"
                    if diff_count > 100:  # max_display_diffs
                        status_text += " (showing first 100 for performance)"
                    status_text += f" - {self.calculate_similarity_message(text1, text2)}"
                    
                    self.status_label.setText(status_text)
                    self.status_label.setStyleSheet(
                        "padding: 10px; border-radius: 5px; background-color: #ffcdd2;"
                    )
            except Exception as e:
                print(f"Error updating status: {e}")
                
        except Exception as e:
            print(f"Error in update_diff_view: {e}")
            self.handle_comparison_error("Error displaying differences")
        finally:
            self.is_processing = False
            
    def calculate_similarity_message(self, text1, text2):
        """Calculate a human-readable similarity message"""
        try:
            if not text1 or not text2:
                return "One text is empty"
                
            # Use quick ratio for better performance
            try:
                matcher = SequenceMatcher(None, text1[:10000], text2[:10000])  # Limit text size for quick calculation
                similarity = matcher.quick_ratio() * 100
            except Exception:
                return "Unable to calculate similarity"
            
            if similarity > 90:
                return f"Texts are very similar ({similarity:.1f}% match)"
            elif similarity > 70:
                return f"Texts have significant differences ({similarity:.1f}% match)"
            elif similarity > 40:
                return f"Texts are quite different ({similarity:.1f}% match)"
            else:
                return f"Texts are very different ({similarity:.1f}% match)"
                
        except Exception as e:
            print(f"Error calculating similarity message: {e}")
            return "Unable to calculate similarity"

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
            # Limit text size for word counting
            text1 = text1[:1000000] if text1 else ""
            text2 = text2[:1000000] if text2 else ""
            
            words1 = len(text1.split()) if text1.strip() else 0
            chars1 = len(text1)
            words2 = len(text2.split()) if text2.strip() else 0
            chars2 = len(text2)
            
            self.word_count1.setText(f"Words: {words1:,}  Characters: {chars1:,}")
            self.word_count2.setText(f"Words: {words2:,}  Characters: {chars2:,}")
        except Exception as e:
            print(f"Error updating word counts: {e}")
            self.word_count1.setText("Words: -  Characters: -")
            self.word_count2.setText("Words: -  Characters: -")

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
