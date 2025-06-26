def json_to_html(data):
    """
    This is straight up ai-generated code.
    """

    html_string = "<table border='1'>"

    # Function to handle nested objects and lists
    def render_row(key, value):
        # If the value is a dictionary, render a nested table
        if isinstance(value, dict):
            return f"<tr><td>{key}</td><td>{json_to_html(value)}</td></tr>"
        # If the value is a list, render each item in the list
        elif isinstance(value, list):
            items = "".join(
                [f"<li>{json_to_html(item) if isinstance(item, (dict, list)) else item}</li>" for item in value])
            return f"<tr><td>{key}</td><td><ul>{items}</ul></td></tr>"
        else:
            # Render the key-value pair in a table row
            return f"<tr><td>{key}</td><td>{value}</td></tr>"

    # Iterate through the JSON object and convert to HTML
    for key, value in data.items():
        html_string += render_row(key, value)

    html_string += "</table>"
    return html_string
