from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'NON-DISCLOSURE AGREEMENT (NDA)', 0, 1, 'C')
        self.ln(10)

pdf = PDF()
pdf.add_page()
pdf.set_font('Arial', '', 12)

content = """
This Non-Disclosure Agreement (the "Agreement") is entered into as of October 1, 2026, by and between:

Party A: Acme Corporation, a Delaware corporation located at 123 Innovation Drive, Tech City, TX.
Party B: John Doe, an independent contractor located at 456 Freelance Way, Dev Town, NY.

1. CONFIDENTIAL INFORMATION
"Confidential Information" means any proprietary information, technical data, trade secrets, or know-how, including, but not limited to, research, product plans, products, services, customers, software, and financial information disclosed by Party A to Party B.

2. OBLIGATIONS OF RECEIVING PARTY
Party B shall hold and maintain the Confidential Information in strictest confidence for the sole and exclusive benefit of Party A. Party B shall carefully restrict access to Confidential Information to employees, contractors, and third parties as is reasonably required.

3. EXCLUSIONS FROM CONFIDENTIAL INFORMATION
Receiving Party's obligations under this Agreement do not extend to information that is: (a) publicly known at the time of disclosure or subsequently becomes publicly known through no fault of the Receiving Party; (b) discovered or created by the Receiving Party before disclosure by Disclosing Party.

4. INDEMNITY AND LIABILITY
Party B agrees to indemnify and hold harmless Party A from any damages, loss, or injury resulting from the breach of this contract. The maximum liability of Party B shall not exceed $50,000.

5. TERM AND TERMINATION
The non-disclosure provisions of this Agreement shall survive the termination of this Agreement and Party B's duty to hold Confidential Information in confidence shall remain in effect in perpetuity. Either party may terminate this Agreement with a 45-day written notice.

6. JURISDICTION
This Agreement shall be governed by and construed in accordance with the laws of the State of Texas without regard to its conflict of law principles. Any arbitration shall take place in Austin, Texas.

IN WITNESS WHEREOF, the parties hereto have executed this Agreement as of the date first written above.

Acme Corporation (Party A)
Signature: ___________________

John Doe (Party B)
Signature: ___________________
"""

for line in content.split('\n'):
    pdf.multi_cell(0, 10, line)

pdf.output('Test_AcmeCorp_NDA.pdf', 'F')
