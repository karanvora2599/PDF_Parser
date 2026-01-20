import fitz
import sys
import os

path = r"C:\Users\karan\Documents\Projects\PDF_Parser\Karan_Vora_Resume_HF.pdf"

if not os.path.exists(path):
    print(f"File not found: {path}")
    sys.exit(1)

doc = fitz.open(path)
page = doc[0]
with open("debug_out.txt", "w", encoding="utf-8") as f:
    f.write(f"Page rect: {page.rect}\n")
    f.write(f"Rotation: {page.rotation}\n")

    blocks = page.get_text("dict")["blocks"]

    f.write(f"Total blocks: {len(blocks)}\n")
    f.write("First 15 blocks (unsorted raw order):\n")
    for i, b in enumerate(blocks[:15]):
        text = ""
        if "lines" in b:
           if b["lines"]:
             if b["lines"][0]["spans"]:
                text = b["lines"][0]["spans"][0]["text"]
        f.write(f"Block {i}: bbox={b['bbox']} text='{text[:30]}...'\n")

    f.write("\nBlocks with 'EXPERIENCE' or job titles:\n")
    for b in blocks:
        text = ""
        if "lines" in b:
            for line in b["lines"]:
                for span in line["spans"]:
                    if "EXPERIENCE" in span["text"] or "LOCOMEX" in span["text"]:
                         f.write(f"Found '{span['text'][:20]}...' at {b['bbox']}\n")
