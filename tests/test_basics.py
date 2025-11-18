"""
Basic unit tests for Power Hour CLI
"""
import pytest
import os
import csv
from pathlib import Path


class TestInputFiles:
    """Test that input CSV files are valid"""
    
    @pytest.fixture
    def input_dir(self):
        return Path(__file__).parent.parent / "input"
    
    def test_input_directory_exists(self, input_dir):
        """Input directory should exist"""
        assert input_dir.exists()
        assert input_dir.is_dir()
    
    def test_csv_files_exist(self, input_dir):
        """Check that CSV playlists exist"""
        csv_files = list(input_dir.glob("*.csv"))
        assert len(csv_files) > 0, "No CSV files found in input directory"
    
    def test_csv_structure(self, input_dir):
        """Each CSV should have proper headers (id, title, start)"""
        # Only check the main playlist files, not legacy ones
        for csv_file in input_dir.glob("*_list.csv"):
            # Skip legacy test files
            if csv_file.name in ['yt_list.csv', 'yt_list_with_times-2.csv']:
                continue
                
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                # Should have id, title, and start columns
                assert 'id' in headers or 'url' in headers, f"{csv_file.name} missing id/url column"
                assert 'title' in headers, f"{csv_file.name} missing title column"
                assert 'start' in headers, f"{csv_file.name} missing start column"
                
                # Check that we have rows
                rows = list(reader)
                assert len(rows) > 0, f"{csv_file.name} has no data rows"
    
    def test_youtube_urls_format(self, input_dir):
        """YouTube URLs should be properly formatted"""
        for csv_file in input_dir.glob("*_list.csv"):
            # Skip legacy test files
            if csv_file.name in ['yt_list.csv', 'yt_list_with_times-2.csv']:
                continue
                
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, start=2):  # start=2 accounts for header
                    url = row.get('id') or row.get('url')
                    
                    # Should be a YouTube URL
                    assert 'youtube.com' in url or 'youtu.be' in url, \
                        f"{csv_file.name} line {i}: Invalid YouTube URL format"
                    
                    # Should NOT have &start_radio=1 (creates random playlists)
                    assert 'start_radio=1' not in url, \
                        f"{csv_file.name} line {i}: URL should not contain start_radio=1"
    
    def test_start_times_valid(self, input_dir):
        """Start times should be valid integers"""
        for csv_file in input_dir.glob("*_list.csv"):
            # Skip legacy test files
            if csv_file.name in ['yt_list.csv', 'yt_list_with_times-2.csv']:
                continue
                
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, start=2):
                    start = row.get('start', '')
                    
                    # Should be a valid integer
                    assert start.isdigit(), \
                        f"{csv_file.name} line {i}: Start time must be an integer"
                    
                    # Should be reasonable (0-300 seconds)
                    start_int = int(start)
                    assert 0 <= start_int <= 300, \
                        f"{csv_file.name} line {i}: Start time should be between 0-300 seconds"


class TestCLI:
    """Test CLI functionality"""
    
    def test_cli_module_imports(self):
        """CLI module should import without errors"""
        from power_hour import cli
        assert cli is not None
    
    def test_builder_module_imports(self):
        """Builder module should import without errors"""
        from power_hour import builder
        assert builder is not None


class TestOutputDirectory:
    """Test output directory structure"""
    
    def test_output_directory_exists(self):
        """Output directory should exist"""
        output_dir = Path(__file__).parent.parent / "output"
        assert output_dir.exists()
        assert output_dir.is_dir()
