"""
AutoBlogger UI Module
GUI 컴포넌트 패키지
"""
# MainWindow is imported conditionally to avoid GUI dependency issues
# in headless environments

__all__ = ['MainWindow']

def get_main_window():
    """
    Lazy import of MainWindow to avoid import errors in headless environments
    """
    from .main_window import MainWindow
    return MainWindow
