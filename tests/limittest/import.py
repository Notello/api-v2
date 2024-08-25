import os
from PyPDF2 import PdfReader, PdfWriter

def split_pdf(input_path, output_folder, pages_per_chunk=3):
    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Read the PDF
    with open(input_path, 'rb') as file:
        pdf = PdfReader(file)
        total_pages = len(pdf.pages)

        # Split the PDF into chunks
        for i in range(0, total_pages, pages_per_chunk):
            print("splitting")
            pdf_writer = PdfWriter()

            # Add pages to the chunk
            for page_num in range(i, min(i + pages_per_chunk, total_pages)):
                pdf_writer.add_page(pdf.pages[page_num])

            # Save the chunk
            output_filename = f'{input_path}_chunk_{i//pages_per_chunk + 1}.pdf'
            output_path = os.path.join(output_folder, output_filename)
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)

    print(f"Split complete. {total_pages} pages split into {(total_pages-1)//pages_per_chunk + 1} chunks.")

# Usage
input_pdf = 'quran.pdf'
output_folder = 'quran'
other_out = 'combined'
split_pdf(input_pdf, output_folder)
split_pdf(input_pdf, other_out)