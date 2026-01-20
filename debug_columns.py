"""Debug column boundary detection."""
import pdfplumber

pdf_path = r"C:\Users\karan\Documents\Projects\PDF_Parser\Deep_Learning___Mini_project.pdf"

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[0]
    words = page.extract_words()
    
    page_width = page.width
    page_center = page_width / 2
    margin = 50
    
    print(f"Page width: {page_width:.0f}, center: {page_center:.0f}")
    print(f"Total words: {len(words)}")
    
    # Count words in left vs right halves
    left_words = [w for w in words if margin < float(w['x0']) < page_center - 20]
    right_words = [w for w in words if page_center + 20 < float(w['x0']) < page_width - margin]
    
    print(f"Left column words: {len(left_words)}")
    print(f"Right column words: {len(right_words)}")
    
    if len(left_words) > 10 and len(right_words) > 10:
        left_max_x = max(float(w['x1']) for w in left_words)
        right_min_x = min(float(w['x0']) for w in right_words)
        gap = right_min_x - left_max_x
        print(f"Left column right edge: {left_max_x:.0f}")
        print(f"Right column left edge: {right_min_x:.0f}")
        print(f"Gap between columns: {gap:.0f}")
    else:
        print("Not enough words in both columns")
