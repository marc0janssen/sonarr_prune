def test_version_format():
    from app.version import __version__

    assert isinstance(__version__, str)
    parts = __version__.split(".")
    assert len(parts) == 3
    for p in parts:
        assert p.isdigit()


def test_package_exports_version():
    import app

    assert app.__version__ == __import__(
        "app.version", fromlist=["__version__"]
    ).__version__
