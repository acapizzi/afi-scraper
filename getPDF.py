import wget
from PyPDF4 import PdfFileReader
from urllib.error import HTTPError

def getPubFile(url):
    try:
        filename = wget.download(url)    
    except HTTPError as e:
        logger.debug('Download error:', e.code, e.read())
    else:
        pdf = PdfFileReader(open(filename, "rb"))
        content = ""
        for i in range (0,pdf.getNumPages()):
            content += pdf.getPage(i).extractText() + " \n"
        return content