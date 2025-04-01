# dua-for-salah-and-supplications
This repository holds code to convert a book from adoc to pdf

# The script to compile this book is

```
#!/usr/bin/env bash

# Check if the input file (.adoc) is provided
if [ -z "$1" ]; then
    echo "Usage: $0 filename.adoc"
    exit 1
fi

# Extract the filename without extension
INPUT_FILE="$1"
BASE_NAME="${INPUT_FILE%.*}"

# Convert .adoc to .html using Asciidoctor
asciidoctor -a linkcss -a copycss -a stylesheet=styles.css "$INPUT_FILE"

# Check if the HTML file was created successfully
if [ ! -f "${BASE_NAME}.html" ]; then
    echo "Failed to generate HTML file from AsciiDoc."
    exit 1
fi

# Convert the HTML file to PDF using Paged.js
pagedjs-cli "${BASE_NAME}.html" -o "${BASE_NAME}.pdf"

# weasyprint "${BASE_NAME}.html" "${BASE_NAME}.pdf"

# chromium --headless --disable-gpu --print-to-pdf="${BASE_NAME}.pdf" --no-pdf-header-footer "file://$(pwd)/${BASE_NAME}.html"

# Check if the PDF file was created successfully
if [ -f "${BASE_NAME}.pdf" ]; then
    echo "PDF generated successfully: ${BASE_NAME}.pdf"
else
    echo "Failed to generate PDF from HTML."
    exit 1
fi

```
