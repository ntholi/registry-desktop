import re


def format_semester(sem: str | None = None, type: str = "full") -> str:
    if sem is None:
        raise ValueError("Semester number cannot be null or undefined")

    sem_str = str(sem)
    letter_match = re.match(r"^([A-Z])(\d+)$", sem_str)

    if letter_match:
        letter = letter_match.group(1)
        number = letter_match.group(2)
        if letter == "F":
            return f"Foundation {number}" if type == "full" else f"F{number}"
        if letter == "B":
            return f"Bridging {number}" if type == "full" else f"B{number}"
        return sem_str

    try:
        sem_number = int(sem_str, 10)
    except ValueError:
        raise ValueError(f"Invalid semester number: {sem}")

    year = (sem_number + 1) // 2
    semester = 2 if sem_number % 2 == 0 else 1

    if type == "full":
        return f"Year {year} • Semester {semester}"
    elif type == "short":
        return f"Year {year} • Sem {semester}"
    else:
        return f"Y{year}S{semester}"
