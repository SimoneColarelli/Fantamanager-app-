import datetime
import math


def format_date_for_display(date_obj):
    """
    Transforms a date object into 'mon-YY' string (Italian abbreviation).
    Example: date(2026, 8, 21) -> 'ago-26'
    """
    if date_obj is None:
        return ""
    
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
    
def from_str_to_trunc_date(value):
    "Convert a string from yyyy-mm-dd formato to truncated date (mon-YY)"
    if not value:
        return None
    try:
        date_obj = datetime.datetime.strptime(value, "%Y-%m-%d")
        return format_date_for_display(date_obj)
    except ValueError:
        return value   