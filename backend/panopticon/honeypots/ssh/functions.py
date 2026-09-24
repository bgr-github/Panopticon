def fix_endline(output: str) -> str:
    """Adds proper endline characters for terminal output

    Args:
        output (str): Input string

    Returns:
        str: Endline fixed string
    """
    if output and not output.endswith(("\n", "\r")):
        output += "\r\n"

    return output
