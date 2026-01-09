#!/bin/bash
# Helper script to URL-encode Mattermost database password

if [ -z "$1" ]; then
    echo "Usage: $0 <password>"
    echo ""
    echo "This script URL-encodes a password for use in MATTERMOST_DB_PASSWORD"
    echo ""
    echo "Example:"
    echo "  $0 'my!@#password'"
    exit 1
fi

python3 << EOF
from urllib.parse import quote
password = "$1"
encoded = quote(password, safe='')
print(f"Original: {password}")
print(f"Encoded:  {encoded}")
print("")
print("Add this to your .env file:")
print(f"MATTERMOST_DB_PASSWORD={encoded}")
EOF
