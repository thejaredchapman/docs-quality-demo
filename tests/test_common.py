from common import split_frontmatter


def test_reads_type_and_body():
    meta, body, offset = split_frontmatter("---\ntype: how-to\n---\n# Title\n")
    assert meta == {"type": "how-to"}
    assert body == "# Title\n"
    assert offset == 3


def test_page_without_frontmatter():
    assert split_frontmatter("# Title\n") == ({}, "# Title\n", 0)


def test_broken_yaml_gives_empty_meta():
    meta, body, _ = split_frontmatter("---\ntype: [oops\n---\n# T\n")
    assert meta == {}
    assert body == "# T\n"


def test_unclosed_frontmatter_is_treated_as_body():
    text = "---\ntype: how-to\n# T\n"
    assert split_frontmatter(text) == ({}, text, 0)
