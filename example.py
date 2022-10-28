from fpdf import FPDF

pdf = FPDF()
pdf.compress = False
# pdf.add_page()
# pdf.set_font('helvetica', size=12)
# pdf.cell(txt="hello world")
# breakpoint()
pdf.close()
pdf.output("hello_world2.pdf")
