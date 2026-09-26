#!/usr/bin/env python3
"""Test PDF export functionality."""

import sys
import os
from datetime import datetime
from pathlib import Path

# Test imports
print("Testing PDF export...")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    print("[OK] ReportLab imports successful")
except ImportError as e:
    print(f"[FAIL] ReportLab not installed: {e}")
    print("Run: pip install reportlab")
    sys.exit(1)

try:
    from PIL import Image
    print("[OK] PIL imported")
except ImportError:
    print("[WARNING] PIL not available - logo may not display")

# Logo path
logo_path = Path(__file__).parent / "logo_new.png"
print(f"Logo path: {logo_path}")
print(f"Logo exists: {logo_path.exists()}")

# Create test PDF
def create_test_pdf():
    output_file = "test_output.pdf"
    
    def add_logo_and_header(canvas_obj, doc):
        canvas_obj.saveState()
        
        # Add logo
        if logo_path.exists():
            try:
                canvas_obj.drawImage(str(logo_path), 30, A4[1] - 80, width=50, height=50,
                                   preserveAspectRatio=True, mask='auto')
                print("[OK] Logo added to page")
            except Exception as e:
                print(f"[WARNING] Logo error: {e}")
        
        # Header text
        canvas_obj.setFont('Helvetica-Bold', 16)
        canvas_obj.setFillColor(colors.HexColor('#1f6feb'))
        canvas_obj.drawString(90, A4[1] - 55, "DR. NILESH SHAH'S MARKET ANALYSIS")
        
        # Line
        canvas_obj.setStrokeColor(colors.HexColor('#1f6feb'))
        canvas_obj.setLineWidth(2)
        canvas_obj.line(30, A4[1] - 90, A4[0] - 30, A4[1] - 90)
        
        # Footer
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.gray)
        canvas_obj.drawString(30, 30, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        canvas_obj.drawRightString(A4[0] - 30, 30, f"Page {doc.page}")
        
        canvas_obj.restoreState()
    
    try:
        doc = SimpleDocTemplate(output_file, pagesize=A4,
                               topMargin=100, bottomMargin=60,
                               leftMargin=30, rightMargin=30)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
                                    fontSize=14, spaceAfter=15, textColor=colors.HexColor('#1f6feb'))
        elements.append(Paragraph("Test PDF Report", title_style))
        elements.append(Spacer(1, 20))
        
        # Test table
        data = [
            ['Symbol', 'Price', 'Score', 'Recommendation'],
            ['RELIANCE', '2500.00', '75.5', 'STRONG BUY'],
            ['TCS', '3800.00', '65.2', 'BUY'],
            ['INFY', '1500.00', '45.0', 'HOLD'],
        ]
        
        table = Table(data, colWidths=[100, 100, 100, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f6feb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
        ]))
        elements.append(table)
        
        # Build PDF
        doc.build(elements, onFirstPage=add_logo_and_header, onLaterPages=add_logo_and_header)
        
        print(f"\n[SUCCESS] PDF created: {output_file}")
        print(f"File size: {os.path.getsize(output_file)} bytes")
        
        # Open file
        if sys.platform == 'win32':
            os.startfile(output_file)
        elif sys.platform == 'darwin':
            os.system(f'open {output_file}')
        else:
            print(f"\nOpen the file: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] PDF creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_test_pdf()
    if success:
        print("\nPDF export is working correctly!")
    else:
        print("\nPDF export has issues - check error above")