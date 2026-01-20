"""Test pdfplumber word extraction for two-column handling."""
import pdfplumber

pdf_path = r"C:\Users\karan\Documents\Projects\PDF_Parser\Deep_Learning___Mini_project.pdf"

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[0]
    
    # Get words with positions
    words = page.extract_words()
    print(f"Total words: {len(words)}")
    
    # Page dimensions
    page_center = page.width / 2
    print(f"Page width: {page.width:.0f}, center: {page_center:.0f}")
    
    # Separate words by column
    left_words = [w for w in words if float(w['x0']) < page_center]
    right_words = [w for w in words if float(w['x0']) >= page_center]
    
    print(f"\nLeft column words: {len(left_words)}")
    print(f"Right column words: {len(right_words)}")
    
    # Sort each column by y position (top)
    left_words.sort(key=lambda w: (float(w['top']), float(w['x0'])))
    right_words.sort(key=lambda w: (float(w['top']), float(w['x0'])))
    
    print("\nFirst 15 words from LEFT column:")
    for w in left_words[:15]:
        print(f"  y={w['top']:.0f}: {w['text']}")
    
    print("\nFirst 15 words from RIGHT column:")
    for w in right_words[:15]:
        print(f"  y={w['top']:.0f}: {w['text']}")
