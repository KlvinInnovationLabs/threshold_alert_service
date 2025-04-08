"""Email content formatting for breach notifications."""

def create_email_subject(breaches):
    """
    Create email subject for breach notifications.
    
    Args:
        breaches: List of breach notifications
        
    Returns:
        str: Email subject
    """
    total_breaches = len(breaches)
    return f"[Threshold Breach Alert] {total_breaches} breach(es) detected."

def create_html_content(breaches):
    """
    Create HTML content for breach notifications.
    
    Args:
        breaches: List of breach notifications
        
    Returns:
        str: HTML content
    """
    # Sort breaches for consistent display
    sorted_breaches = sorted(
        breaches,
        key=lambda x: (
            x["timestamp"],
            x["factory_name"],
            x["zone_name"],
            x["device_id"],
            x["sensor_id"],
        ),
    )
    
    # Generate HTML rows for each breach
    breaches_html_output = ""
    for breach in sorted_breaches:
        breaches_html_output += (
            f"<tr>"
            f"    <td>{breach['factory_name']}</td>"
            f"    <td>{breach['zone_name']}</td>"
            f"    <td>{breach['machine_name']}</td>"
            f"    <td>{breach['device_id']}</td>"
            f"    <td>{breach['sensor_name']}</td>"
            f"    <td>{breach['sensor_value']}</td>"
            f"    <td>{breach['threshold_type']}</td>"
            f"    <td>{breach['threshold_value']}</td>"
            f"    <td>{breach['timestamp']}</td>"
            f"</tr>"
        )
    
    # Generate complete HTML
    html_content = f"""
    <html>
    <head>
        <style>
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            th, td {{
                border: 1px solid black;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
        </style>
    </head>
    <body>
        <p><strong>Attention:</strong></p>
        <p>The following devices have crossed their standard thresholds:</p>

        <table>
            <thead>
                <tr>
                    <th>Factory Name</th>
                    <th>Zone Name</th>
                    <th>Machine Name</th>
                    <th>Device ID</th>
                    <th>Sensor Name</th>
                    <th>Sensor Value</th>
                    <th>Threshold Breached</th>
                    <th>Threshold Value</th>
                    <th>Timestamp</th>
                </tr>
            </thead>
            <tbody>
                {breaches_html_output}
            </tbody>
        </table>

        <br><br>
        <p>Regards,<br><strong>Klvin Support Team</strong></p>
    </body>
    </html>
    """
    
    return html_content