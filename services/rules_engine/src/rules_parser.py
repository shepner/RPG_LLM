"""Rules file parser and content extractor."""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import markdown
import yaml
import json

# PDF extraction
try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# EPUB extraction
try:
    import ebooklib
    from ebooklib import epub
    EPUB_AVAILABLE = True
except ImportError:
    EPUB_AVAILABLE = False


class RulesParser:
    """Parses rules files and extracts content for LLM use."""
    
    def __init__(self, rules_dir: Path):
        """Initialize parser."""
        self.rules_dir = rules_dir
    
    def extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text content from PDF file."""
        if not PDF_AVAILABLE:
            return "PDF extraction not available. Please install PyPDF2."
        
        try:
            reader = PdfReader(str(file_path))
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text())
            return "\n\n".join(text_parts)
        except Exception as e:
            return f"Error extracting PDF: {str(e)}"
    
    def extract_text_from_epub(self, file_path: Path) -> str:
        """Extract text content from EPUB file."""
        if not EPUB_AVAILABLE:
            return "EPUB extraction not available. Please install ebooklib."
        
        try:
            book = epub.read_epub(str(file_path))
            text_parts = []
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    # Extract text from HTML content
                    content = item.get_content().decode('utf-8')
                    # Simple HTML tag removal (basic)
                    import re
                    text = re.sub(r'<[^>]+>', '', content)
                    text_parts.append(text)
            return "\n\n".join(text_parts)
        except Exception as e:
            return f"Error extracting EPUB: {str(e)}"
    
    def parse_markdown(self, content: str) -> Dict[str, Any]:
        """Parse Markdown file and extract structured content."""
        try:
            # Convert markdown to HTML for structure analysis
            html = markdown.markdown(content, extensions=['tables', 'fenced_code'])
            
            # Extract sections (headers)
            sections = {}
            current_section = "Introduction"
            current_content = []
            
            for line in content.split('\n'):
                if line.startswith('#'):
                    if current_content:
                        sections[current_section] = '\n'.join(current_content)
                    current_section = line.lstrip('#').strip()
                    current_content = []
                else:
                    current_content.append(line)
            
            if current_content:
                sections[current_section] = '\n'.join(current_content)
            
            return {
                "raw_content": content,
                "html": html,
                "sections": sections,
                "type": "markdown"
            }
        except Exception as e:
            return {
                "raw_content": content,
                "error": str(e),
                "type": "markdown"
            }
    
    def parse_yaml(self, content: str) -> Dict[str, Any]:
        """Parse YAML file."""
        try:
            data = yaml.safe_load(content)
            return {
                "raw_content": content,
                "parsed": data,
                "type": "yaml"
            }
        except Exception as e:
            return {
                "raw_content": content,
                "error": str(e),
                "type": "yaml"
            }
    
    def parse_json(self, content: str) -> Dict[str, Any]:
        """Parse JSON file."""
        try:
            data = json.loads(content)
            return {
                "raw_content": content,
                "parsed": data,
                "type": "json"
            }
        except Exception as e:
            return {
                "raw_content": content,
                "error": str(e),
                "type": "json"
            }
    
    def extract_content(self, file_path: Path, file_type: str) -> Dict[str, Any]:
        """
        Extract content from a rules file.
        
        Args:
            file_path: Path to the file
            file_type: File extension (e.g., '.pdf', '.md', '.yaml')
            
        Returns:
            Dictionary with extracted content and metadata
        """
        result = {
            "file_path": str(file_path),
            "file_type": file_type,
            "content": "",
            "parsed": None
        }
        
        if file_type in {'.pdf'}:
            result["content"] = self.extract_text_from_pdf(file_path)
            result["parsed"] = {"type": "pdf", "extracted_text": result["content"]}
        
        elif file_type in {'.epub'}:
            result["content"] = self.extract_text_from_epub(file_path)
            result["parsed"] = {"type": "epub", "extracted_text": result["content"]}
        
        elif file_type in {'.md', '.markdown'}:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            result["content"] = content
            result["parsed"] = self.parse_markdown(content)
        
        elif file_type in {'.yaml', '.yml'}:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            result["content"] = content
            result["parsed"] = self.parse_yaml(content)
        
        elif file_type in {'.json'}:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            result["content"] = content
            result["parsed"] = self.parse_json(content)
        
        elif file_type in {'.txt'}:
            with open(file_path, 'r', encoding='utf-8') as f:
                result["content"] = f.read()
            result["parsed"] = {"type": "text", "content": result["content"]}
        
        else:
            result["content"] = f"Unsupported file type: {file_type}"
            result["parsed"] = {"type": "unknown", "error": "Unsupported file type"}
        
        return result

