def format_semester(sem: int | None, type: str = "full") -> str:
    """
    Format semester number into human-readable format.

    Args:
        sem: Semester number (1-based) or None
        type: Format type - 'full' (Year X • Semester Y),
              'short' (Year X • Sem Y), or 'mini' (YXS Y)

    Returns:
        Formatted semester string or empty string if sem is None
    """
    if not sem:
        return ""

    year = -(-sem // 2)  # Ceiling division
    semester = 2 if sem % 2 == 0 else 1

    if type == "full":
        return f"Year {year} • Semester {semester}"
    elif type == "short":
        return f"Year {year} • Sem {semester}"
    else:  # mini
        return f"Y{year}S{semester}"
