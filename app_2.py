import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QTextEdit, QLabel, QPushButton, 
                           QProgressBar, QFrame, QScrollBar, QMessageBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPalette, QFont, QIcon
import difflib

class TextComparisonApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Text Comparison Tool")
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            QWidget {
                font-family: 'Segoe UI';
            }
            QTextEdit {
                background-color: white;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                padding: 12px;
                font-size: 12pt;
                selection-background-color: #e3f2fd;
            }
            QTextEdit:focus {
                border: 2px solid #1a73e8;
            }
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
            QPushButton#helpButton {
                background-color: #34a853;
            }
            QPushButton#helpButton:hover {
                background-color: #2d8d47;
            }
            QLabel {
                font-size: 11pt;
                color: #202124;
            }
            QLabel#headerLabel {
                font-size: 14pt;
                font-weight: bold;
                color: #1a73e8;
                padding: 10px;
            }
            QLabel#descriptionLabel {
                font-size: 10pt;
                color: #5f6368;
                padding: 5px;
            }
            QProgressBar {
                border: 2px solid #e9ecef;
                border-radius: 6px;
                text-align: center;
                height: 25px;
                font-weight: bold;
                font-size: 10pt;
            }
            QProgressBar::chunk {
                background-color: #1a73e8;
                border-radius: 4px;
            }
            QFrame#separator {
                background-color: #e9ecef;
                max-height: 1px;
            }
        """)

        # Initialize settings
        self.case_sensitive = True
        self.ignore_whitespace = False
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.compare_texts)

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Add header section
        self.create_header_section(layout)

        # Create separator
        separator = QFrame()
        separator.setObjectName("separator")
        layout.addWidget(separator)

        # Create input section
        input_layout = QHBoxLayout()
        input_layout.setSpacing(20)
        
        # Original text section
        original_layout = QVBoxLayout()
        self.original_label = QLabel("Original Text")
        self.original_text = QTextEdit()
        self.original_text.setPlaceholderText("Enter or paste your original text here...")
        self.original_text.textChanged.connect(self.on_text_change)
        self.original_text.setAcceptRichText(False)  # Disable rich text
        self.original_text.setTextColor(QColor("#202124"))  # Set default text color
        original_layout.addWidget(self.original_label)
        original_layout.addWidget(self.original_text)
        
        # Comparison text section
        comparison_layout = QVBoxLayout()
        self.comparison_label = QLabel("Comparison Text")
        self.comparison_text = QTextEdit()
        self.comparison_text.setPlaceholderText("Enter or paste your comparison text here...")
        self.comparison_text.textChanged.connect(self.on_text_change)
        self.comparison_text.setAcceptRichText(False)  # Disable rich text
        self.comparison_text.setTextColor(QColor("#202124"))  # Set default text color
        comparison_layout.addWidget(self.comparison_label)
        comparison_layout.addWidget(self.comparison_text)

        input_layout.addLayout(original_layout)
        input_layout.addLayout(comparison_layout)
        layout.addLayout(input_layout)

        # Create progress section with improved styling
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 10, 0, 10)
        self.similarity_label = QLabel("Similarity: 0.0%")
        self.similarity_label.setStyleSheet("font-weight: bold;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        progress_layout.addWidget(self.similarity_label)
        progress_layout.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(progress_layout)

        # Create difference display section
        diff_layout = QHBoxLayout()
        diff_layout.setSpacing(20)
        
        # Original text differences
        self.original_diff = QTextEdit()
        self.original_diff.setReadOnly(True)
        
        # Comparison text differences
        self.comparison_diff = QTextEdit()
        self.comparison_diff.setReadOnly(True)
        
        diff_layout.addWidget(self.original_diff)
        diff_layout.addWidget(self.comparison_diff)
        layout.addLayout(diff_layout)

        # Create control buttons with improved layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_fields)
        
        self.case_button = QPushButton("Case Sensitivity: On")
        self.case_button.clicked.connect(self.toggle_case_sensitivity)
        
        self.whitespace_button = QPushButton("Whitespace: On")
        self.whitespace_button.clicked.connect(self.toggle_whitespace_sensitivity)

        self.help_button = QPushButton("Help")
        self.help_button.setObjectName("helpButton")
        self.help_button.clicked.connect(self.show_help)
        
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.case_button)
        button_layout.addWidget(self.whitespace_button)
        button_layout.addStretch()
        button_layout.addWidget(self.help_button)
        layout.addLayout(button_layout)

        # Create legend with improved styling
        legend_layout = QHBoxLayout()
        legend_label = QLabel("Legend:")
        legend_label.setStyleSheet("font-weight: bold;")
        
        matching_label = QLabel("Matching Text")
        matching_label.setStyleSheet("""
            background-color: #e8f5e9;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 10pt;
        """)
        
        added_label = QLabel("Added/Changed Text")
        added_label.setStyleSheet("""
            background-color: #fff3e0;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 10pt;
        """)
        
        legend_layout.addWidget(legend_label)
        legend_layout.addWidget(matching_label)
        legend_layout.addWidget(added_label)
        legend_layout.addStretch()
        layout.addLayout(legend_layout)

        # Set up synchronized scrolling
        self.setup_synchronized_scrolling()

        # Set window size
        self.resize(1400, 1000)

    def create_header_section(self, layout):
        header_layout = QVBoxLayout()
        
        # Main title
        header_label = QLabel("Advanced Text Comparison Tool")
        header_label.setObjectName("headerLabel")
        header_layout.addWidget(header_label)
        
        # Description
        description_label = QLabel(
            "Compare two texts and visualize their differences in real-time. "
            "Use the controls below to customize the comparison settings."
        )
        description_label.setObjectName("descriptionLabel")
        description_label.setWordWrap(True)
        header_layout.addWidget(description_label)
        
        layout.addLayout(header_layout)

    def show_help(self):
        help_text = """
<h2>How to Use the Text Comparison Tool</h2>

<h3>Basic Usage:</h3>
<ul>
    <li>Enter or paste text in both text boxes</li>
    <li>The comparison updates automatically as you type</li>
    <li>Differences are highlighted in real-time</li>
</ul>

<h3>Features:</h3>
<ul>
    <li><b>Case Sensitivity:</b> Toggle whether capitalization matters in comparison</li>
    <li><b>Whitespace Sensitivity:</b> Toggle whether spaces and line breaks matter</li>
    <li><b>Real-time Updates:</b> See changes as you type</li>
    <li><b>Similarity Score:</b> View how similar the texts are as a percentage</li>
</ul>

<h3>Understanding the Display:</h3>
<ul>
    <li>Red highlighting shows removed or changed text</li>
    <li>Green highlighting shows added or changed text</li>
    <li>Matching text remains unhighlighted</li>
</ul>
"""
        msg = QMessageBox()
        msg.setWindowTitle("Help - Text Comparison Tool")
        msg.setTextFormat(Qt.RichText)
        msg.setText(help_text)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: white;
            }
            QMessageBox QLabel {
                font-size: 11pt;
                color: #202124;
            }
        """)
        msg.exec_()

    def setup_synchronized_scrolling(self):
        # Synchronize vertical scrolling
        self.original_text.verticalScrollBar().valueChanged.connect(
            lambda val: self.sync_scroll(val, [
                self.comparison_text.verticalScrollBar(),
                self.original_diff.verticalScrollBar(),
                self.comparison_diff.verticalScrollBar()
            ])
        )
        self.comparison_text.verticalScrollBar().valueChanged.connect(
            lambda val: self.sync_scroll(val, [
                self.original_text.verticalScrollBar(),
                self.original_diff.verticalScrollBar(),
                self.comparison_diff.verticalScrollBar()
            ])
        )
        self.original_diff.verticalScrollBar().valueChanged.connect(
            lambda val: self.sync_scroll(val, [
                self.original_text.verticalScrollBar(),
                self.comparison_text.verticalScrollBar(),
                self.comparison_diff.verticalScrollBar()
            ])
        )
        self.comparison_diff.verticalScrollBar().valueChanged.connect(
            lambda val: self.sync_scroll(val, [
                self.original_text.verticalScrollBar(),
                self.comparison_text.verticalScrollBar(),
                self.original_diff.verticalScrollBar()
            ])
        )

    def sync_scroll(self, value, scrollbars):
        for scrollbar in scrollbars:
            scrollbar.setValue(value)

    def on_text_change(self):
        # Reset the timer to prevent multiple rapid updates
        self.update_timer.stop()
        self.update_timer.start(1000)  # Wait for 1 second of no changes before updating

    def standardize_text(self, text):
        # Only standardize line endings
        return text.replace('\r\n', '\n').replace('\r', '\n')

    def compare_texts(self):
        # Get input texts with minimal standardization
        text1 = self.original_text.toPlainText()
        text2 = self.comparison_text.toPlainText()
        
        if not text1 and not text2:
            self.progress_bar.setValue(0)
            self.similarity_label.setText("Similarity: 0.0%")
            self.original_diff.clear()
            self.comparison_diff.clear()
            return
        
        # Create comparison texts based on settings
        comp_text1 = text1
        comp_text2 = text2
        
        if not self.case_sensitive:
            comp_text1 = comp_text1.lower()
            comp_text2 = comp_text2.lower()
            
        if self.ignore_whitespace:
            comp_text1 = ''.join(comp_text1.split())
            comp_text2 = ''.join(comp_text2.split())
        
        # Calculate similarity using the modified texts
        matcher = difflib.SequenceMatcher(None, comp_text1, comp_text2)
        similarity = matcher.ratio() * 100
        
        # Update progress
        self.progress_bar.setValue(int(similarity))
        self.similarity_label.setText(f"Similarity: {similarity:.1f}%")
        
        # Update difference displays using original texts for display
        self.update_diff_display(text1, text2, matcher)

    def update_diff_display(self, text1, text2, matcher):
        # Store current scroll positions
        original_scroll = self.original_diff.verticalScrollBar().value()
        comparison_scroll = self.comparison_diff.verticalScrollBar().value()
        
        # Clear and insert text
        self.original_diff.clear()
        self.comparison_diff.clear()
        self.original_diff.insertPlainText(text1)
        self.comparison_diff.insertPlainText(text2)
        
        # Apply formatting
        original_cursor = self.original_diff.textCursor()
        comparison_cursor = self.comparison_diff.textCursor()
        
        format_match = self.original_diff.currentCharFormat()
        format_match.setBackground(QColor("#e8f5e9"))  # Green for matches
        
        format_diff = self.comparison_diff.currentCharFormat()
        format_diff.setBackground(QColor("#fff3e0"))  # Yellow for differences
        
        # Clear any existing formatting
        original_cursor.select(original_cursor.Document)
        original_cursor.setCharFormat(self.original_diff.currentCharFormat())
        comparison_cursor.select(comparison_cursor.Document)
        comparison_cursor.setCharFormat(self.comparison_diff.currentCharFormat())

        # Apply highlighting
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # Highlight matching sections in green
                original_cursor.setPosition(i1)
                original_cursor.setPosition(i2, original_cursor.KeepAnchor)
                original_cursor.mergeCharFormat(format_match)
                
                comparison_cursor.setPosition(j1)
                comparison_cursor.setPosition(j2, comparison_cursor.KeepAnchor)
                comparison_cursor.mergeCharFormat(format_match)
            else:
                # Highlight differences in yellow
                if tag in ('replace', 'delete'):
                    original_cursor.setPosition(i1)
                    original_cursor.setPosition(i2, original_cursor.KeepAnchor)
                    original_cursor.mergeCharFormat(format_diff)
                
                if tag in ('replace', 'insert'):
                    comparison_cursor.setPosition(j1)
                    comparison_cursor.setPosition(j2, comparison_cursor.KeepAnchor)
                    comparison_cursor.mergeCharFormat(format_diff)
        
        # Restore scroll positions
        self.original_diff.verticalScrollBar().setValue(original_scroll)
        self.comparison_diff.verticalScrollBar().setValue(comparison_scroll)

    def reset_fields(self):
        self.original_text.clear()
        self.comparison_text.clear()
        self.original_diff.clear()
        self.comparison_diff.clear()
        self.progress_bar.setValue(0)
        self.similarity_label.setText("Similarity: 0.0%")

    def toggle_case_sensitivity(self):
        self.case_sensitive = not self.case_sensitive
        self.case_button.setText(f"Case Sensitivity: {'On' if self.case_sensitive else 'Off'}")
        self.compare_texts()

    def toggle_whitespace_sensitivity(self):
        self.ignore_whitespace = not self.ignore_whitespace
        self.whitespace_button.setText(f"Whitespace: {'On' if not self.ignore_whitespace else 'Off'}")
        self.compare_texts()

def main():
    app = QApplication(sys.argv)
    window = TextComparisonApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
