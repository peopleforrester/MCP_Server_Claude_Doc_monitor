# ABOUTME: Unit tests for the input handler module.
# ABOUTME: Tests markdown parsing and claim extraction functionality.

import pytest
from pathlib import Path
from analyzer.input_handler import (
    load_markdown_file,
    parse_sections,
    extract_claims,
    Claim,
    Section,
)


class TestLoadMarkdownFile:
    """Tests for loading markdown files."""

    def test_load_existing_file(self, tmp_path: Path) -> None:
        """Should load content from an existing markdown file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\nSome content")

        content = load_markdown_file(test_file)

        assert content == "# Test\nSome content"

    def test_load_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing files."""
        nonexistent = tmp_path / "missing.md"

        with pytest.raises(FileNotFoundError):
            load_markdown_file(nonexistent)

    def test_load_empty_file(self, tmp_path: Path) -> None:
        """Should return empty string for empty files."""
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")

        content = load_markdown_file(empty_file)

        assert content == ""


class TestParseSections:
    """Tests for parsing markdown into sections."""

    def test_parse_single_section(self) -> None:
        """Should parse a single header section."""
        content = "# Header\nSome content here."

        sections = parse_sections(content)

        assert len(sections) == 1
        assert sections[0].title == "Header"
        assert sections[0].content == "Some content here."
        assert sections[0].level == 1
        assert sections[0].start_line == 1

    def test_parse_multiple_sections(self) -> None:
        """Should parse multiple sections at different levels."""
        content = """# Main Title
Introduction text.

## Section One
First section content.

## Section Two
Second section content.
"""
        sections = parse_sections(content)

        assert len(sections) == 3
        assert sections[0].title == "Main Title"
        assert sections[0].level == 1
        assert sections[1].title == "Section One"
        assert sections[1].level == 2
        assert sections[2].title == "Section Two"
        assert sections[2].level == 2

    def test_parse_nested_sections(self) -> None:
        """Should correctly handle nested header levels."""
        content = """# Top
## Sub
### SubSub
Content here.
"""
        sections = parse_sections(content)

        assert len(sections) == 3
        assert sections[0].level == 1
        assert sections[1].level == 2
        assert sections[2].level == 3

    def test_parse_content_before_first_header(self) -> None:
        """Should capture content before the first header as intro section."""
        content = """Some intro text.

# First Header
Section content.
"""
        sections = parse_sections(content)

        assert len(sections) == 2
        assert sections[0].title == "(Introduction)"
        assert "intro text" in sections[0].content

    def test_parse_empty_content(self) -> None:
        """Should return empty list for empty content."""
        sections = parse_sections("")

        assert sections == []

    def test_section_tracks_line_numbers(self) -> None:
        """Should track the starting line number for each section."""
        content = """# First
Line two.
Line three.

# Second
Line six.
"""
        sections = parse_sections(content)

        assert sections[0].start_line == 1
        assert sections[1].start_line == 5


class TestExtractClaims:
    """Tests for extracting capability claims from sections."""

    def test_extract_capability_claim(self) -> None:
        """Should extract 'Claude can...' style claims."""
        section = Section(
            title="Features",
            content="Claude can process up to 200k tokens in a single request.",
            level=2,
            start_line=1
        )

        claims = extract_claims([section])

        assert len(claims) >= 1
        assert any("200k tokens" in c.text for c in claims)

    def test_extract_api_syntax_claim(self) -> None:
        """Should extract API syntax claims."""
        section = Section(
            title="API Usage",
            content="Use the `system` parameter to set the system prompt.",
            level=2,
            start_line=1
        )

        claims = extract_claims([section])

        assert len(claims) >= 1
        assert any("system" in c.text.lower() for c in claims)

    def test_extract_numeric_limit_claim(self) -> None:
        """Should extract claims with numeric limits."""
        section = Section(
            title="Limits",
            content="The maximum context window is 100k tokens.",
            level=2,
            start_line=5
        )

        claims = extract_claims([section])

        assert len(claims) >= 1
        assert any("100k" in c.text for c in claims)

    def test_claim_includes_section_context(self) -> None:
        """Each claim should reference its source section."""
        section = Section(
            title="API Guide",
            content="Claude supports streaming responses.",
            level=2,
            start_line=10
        )

        claims = extract_claims([section])

        assert len(claims) >= 1
        assert claims[0].section_title == "API Guide"

    def test_claim_includes_line_number(self) -> None:
        """Each claim should include approximate line number."""
        section = Section(
            title="Features",
            content="Claude can analyze images.",
            level=2,
            start_line=15
        )

        claims = extract_claims([section])

        assert len(claims) >= 1
        assert claims[0].line_number >= 15

    def test_extract_no_claims_from_generic_text(self) -> None:
        """Should not extract claims from non-capability text."""
        section = Section(
            title="Introduction",
            content="Welcome to this tutorial. We hope you enjoy learning.",
            level=1,
            start_line=1
        )

        claims = extract_claims([section])

        # Generic welcome text shouldn't produce capability claims
        assert len(claims) == 0

    def test_extract_multiple_claims_from_section(self) -> None:
        """Should extract multiple claims from a single section."""
        section = Section(
            title="Capabilities",
            content="""Claude can process images and documents.
The API supports both sync and async modes.
Maximum output is 4096 tokens per response.""",
            level=2,
            start_line=1
        )

        claims = extract_claims([section])

        assert len(claims) >= 2

    def test_extract_claims_from_multiple_sections(self) -> None:
        """Should extract claims across all provided sections."""
        sections = [
            Section("Features", "Claude supports vision capabilities.", 2, 1),
            Section("Limits", "Rate limit is 60 requests per minute.", 2, 10),
        ]

        claims = extract_claims(sections)

        assert len(claims) >= 2


class TestClaimDataClass:
    """Tests for the Claim data structure."""

    def test_claim_has_required_fields(self) -> None:
        """Claim should have text, section_title, and line_number."""
        claim = Claim(
            text="Claude can do X",
            section_title="Features",
            line_number=5
        )

        assert claim.text == "Claude can do X"
        assert claim.section_title == "Features"
        assert claim.line_number == 5


class TestSectionDataClass:
    """Tests for the Section data structure."""

    def test_section_has_required_fields(self) -> None:
        """Section should have title, content, level, and start_line."""
        section = Section(
            title="Test",
            content="Content",
            level=2,
            start_line=10
        )

        assert section.title == "Test"
        assert section.content == "Content"
        assert section.level == 2
        assert section.start_line == 10
