# test_pdf.py
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

buffer = BytesIO()
doc = SimpleDocTemplate(buffer, pagesize=A4)
styles = getSampleStyleSheet()
elements = []
elements.append(Paragraph("Test PDF Generation", styles['Title']))
doc.build(elements)

print("✓ PDF generation is working!")
print(f"✓ Generated {len(buffer.getvalue())} bytes")