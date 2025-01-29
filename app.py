from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QTextEdit)
from PyQt5.QtGui import QTextCharFormat, QColor, QSyntaxHighlighter, QFont
from PyQt5.QtCore import Qt, QTimer
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
        self.update_timer.start(300)

    def standardize_text(self, text):
        """Standardize text formatting regardless of input source"""
        # Remove any special Unicode whitespace characters
        text = ' '.join(text.split())
        return text

    def update_comparison(self):
        # Store current positions
        scroll1 = self.text1.verticalScrollBar().value()
        scroll2 = self.text2.verticalScrollBar().value()
        scroll_diff = self.diff_view.verticalScrollBar().value()
        cursor1_pos = self.text1.textCursor().position()
        cursor2_pos = self.text2.textCursor().position()
        
        self.highlighter1.enabled = False
        self.highlighter2.enabled = False
        
        # Get and standardize the text from both editors
        text1 = self.standardize_text(self.text1.toPlainText())
        text2 = self.standardize_text(self.text2.toPlainText())
        
        # Update the text editors with standardized text without triggering the update
        self.text1.blockSignals(True)
        self.text2.blockSignals(True)
        self.text1.setPlainText(text1)
        self.text2.setPlainText(text2)
        
        # Restore cursor positions
        cursor1 = self.text1.textCursor()
        cursor2 = self.text2.textCursor()
        cursor1.setPosition(min(cursor1_pos, len(text1)))
        cursor2.setPosition(min(cursor2_pos, len(text2)))
        self.text1.setTextCursor(cursor1)
        self.text2.setTextCursor(cursor2)
        
        self.text1.blockSignals(False)
        self.text2.blockSignals(False)
        
        # Restore scroll positions
        self.text1.verticalScrollBar().setValue(scroll1)
        self.text2.verticalScrollBar().setValue(scroll2)
        
        # Update word counts
        words1 = len(text1.split()) if text1.strip() else 0
        chars1 = len(text1)
        words2 = len(text2.split()) if text2.strip() else 0
        chars2 = len(text2)
        
        self.word_count1.setText(f"Words: {words1}  Characters: {chars1}")
        self.word_count2.setText(f"Words: {words2}  Characters: {chars2}")
        
        # Update highlighters
        self.highlighter1.set_other_text(text2)
        self.highlighter2.set_other_text(text1)
        
        # Before updating diff view, store its content
        diff_content = []
        matcher = SequenceMatcher(None, text1, text2)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue
            elif tag == 'delete':
                diff_content.append(f'Deleted: "{text1[i1:i2]}" at position {i1}')
            elif tag == 'insert':
                diff_content.append(f'Inserted: "{text2[j1:j2]}" at position {j1}')
            elif tag == 'replace':
                diff_content.append(f'Changed: "{text1[i1:i2]}" → "{text2[j1:j2]}"')
        
        # Update diff view while maintaining scroll position
        self.diff_view.clear()
        for line in diff_content:
            self.diff_view.append(line)
        self.diff_view.verticalScrollBar().setValue(scroll_diff)
        
        self.highlighter1.enabled = True
        self.highlighter2.enabled = True
        self.highlighter1.rehighlight()
        self.highlighter2.rehighlight()
        
        # Update status
        if not text1 and not text2:
            self.status_label.setText("Enter text to compare")
            self.status_label.setStyleSheet("padding: 10px; border-radius: 5px; background-color: #e3f2fd;")
        elif text1 == text2:
            self.status_label.setText("✓ Texts are identical")
            self.status_label.setStyleSheet("padding: 10px; border-radius: 5px; background-color: #c8e6c9;")
        else:
            diff_count = sum(1 for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != 'equal')
            self.status_label.setText(f"⚠ Texts are different (Found {diff_count} differences)")
            self.status_label.setStyleSheet("padding: 10px; border-radius: 5px; background-color: #ffcdd2;")

    def create_text_edit(self, font_size=11):
        """Create a QTextEdit with proper scroll behavior"""
        text_edit = QTextEdit()
        text_edit.setFont(QFont("Consolas", font_size))
        text_edit.setAcceptRichText(False)
        
        # Get the vertical scrollbar
        scrollbar = text_edit.verticalScrollBar()
        
        # Store the current cursor position
        last_cursor_pos = 0
        
        def store_cursor_pos():
            nonlocal last_cursor_pos
            last_cursor_pos = text_edit.textCursor().position()
        
        # Prevent automatic scrolling by maintaining scroll position and cursor
        def maintain_scroll(value):
            if not text_edit.hasFocus():
                scrollbar.setValue(value)
                # Restore cursor position
                cursor = text_edit.textCursor()
                cursor.setPosition(last_cursor_pos)
                text_edit.setTextCursor(cursor)
        
        # Connect signals
        scrollbar.valueChanged.connect(maintain_scroll)
        text_edit.cursorPositionChanged.connect(store_cursor_pos)
        
        return text_edit

def main():
    app = QApplication(sys.argv)
    window = StringComparisonApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
