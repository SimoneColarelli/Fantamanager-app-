import math


def format_date_for_display(date_obj):
    """Format a date object to a string in 'YYYY-MM-DD' format for display."""
    if date_obj is None:
        return ""
    """
    Transforms a date object into 'mon-YY' string (Italian abbreviation).
    Example: date(2026, 8, 21) -> 'ago-26'
    """
    # Map month numbers to Italian short names
    months = {
        1: "gen", 2: "feb", 3: "mar", 4: "apr",
        5: "mag", 6: "giu", 7: "lug", 8: "ago",
        9: "set", 10: "ott", 11: "nov", 12: "dic"
    }
    
    # Get the Italian month name and the last two digits of the year
    month_short = months[date_obj.month]
    year_short = date_obj.strftime("%y")
    
    return f"{month_short}-{year_short}"

def format_boolean_for_display(value):
    """Format a boolean value to 'Sì' or 'No' for display."""
    if value is True:
        return "Sì"
    elif value is False:
        return "No"
    return ""

def format_value_for_display(value):
    """Format a value for display based on its type."""
    if value is None:
        return ""
    elif isinstance(value, bool):
        return format_boolean_for_display(value)
    elif hasattr(value, 'strftime'):
        return format_date_for_display(value)
    elif isinstance(value, (int, float)):
        return str(math.trunc(value))
    else:
        return str(value)