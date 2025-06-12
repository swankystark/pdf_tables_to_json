from pdf2docx import Converter

pdf_file = "2024-08-01-ACT-Compensation.pdf"
word_file = "2024-08-01-ACT-Compensation.docx"

cv = Converter(pdf_file)
cv.convert(word_file, start=0, end=None)  # convert all pages
cv.close()
