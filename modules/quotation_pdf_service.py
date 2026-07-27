from io import BytesIO
from datetime import datetime
from typing import Dict, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os


class QuotationPDFService:
    def __init__(self):
        self._register_fonts()

    def _register_fonts(self):
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc"
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    if font_path.endswith("msyh.ttc"):
                        pdfmetrics.registerFont(TTFont('MicrosoftYaHei', font_path))
                    elif font_path.endswith("msyhbd.ttc"):
                        pdfmetrics.registerFont(TTFont('MicrosoftYaHeiBold', font_path))
                    elif font_path.endswith("simhei.ttf"):
                        pdfmetrics.registerFont(TTFont('SimHei', font_path))
                    elif font_path.endswith("simsun.ttc"):
                        pdfmetrics.registerFont(TTFont('SimSun', font_path))
                except Exception:
                    pass

    def export_quotation(self, quotation_data: Dict) -> BytesIO:
        buffer = BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=20*mm,
            rightMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        elements = []
        
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'Title',
            fontName='MicrosoftYaHeiBold' if 'MicrosoftYaHeiBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
            fontSize=18,
            alignment=1,
            spaceAfter=15
        )
        
        header_style = ParagraphStyle(
            'Header',
            fontName='MicrosoftYaHeiBold' if 'MicrosoftYaHeiBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
            fontSize=12,
            alignment=0,
            spaceAfter=5
        )
        
        normal_style = ParagraphStyle(
            'Normal',
            fontName='MicrosoftYaHei' if 'MicrosoftYaHei' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
            fontSize=10,
            alignment=0,
            spaceAfter=5
        )
        
        elements.append(Paragraph("JAX 小鼠活鼠报价单", title_style))
        elements.append(Spacer(1, 20))
        
        customer_info = quotation_data.get("customer_info", {})
        quote_number = quotation_data.get("quote_number", "")
        quote_date = quotation_data.get("quote_date", datetime.now().strftime("%Y-%m-%d"))
        
        customer_data = [
            ["客户名称:", customer_info.get("customer_name", "")],
            ["联系人:", customer_info.get("contact_person", "")],
            ["销售:", customer_info.get("sales_person", "")],
            ["客户类型:", self._get_customer_type_label(customer_info.get("customer_type", ""))],
            ["报价日期:", quote_date],
            ["报价单号:", quote_number]
        ]
        
        customer_table = Table(customer_data, colWidths=[80, 250])
        customer_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'MicrosoftYaHei' if 'MicrosoftYaHei' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('SPACING', (0, 0), (-1, -1), 5)
        ]))
        
        elements.append(customer_table)
        elements.append(Spacer(1, 20))
        
        elements.append(Paragraph("报价明细:", header_style))
        elements.append(Spacer(1, 10))
        
        items = quotation_data.get("items", [])
        
        if items:
            table_data = [["序号", "品系号", "品系名称", "基因型", "周龄", "性别", "数量", "单价", "金额"]]
            
            for i, item in enumerate(items):
                row = [
                    str(i + 1),
                    item.get("strain", ""),
                    item.get("name", ""),
                    item.get("genotype", ""),
                    item.get("age", ""),
                    item.get("sex", ""),
                    str(item.get("qty", 0)),
                    f"{item.get('unit_price', 0):,.2f}",
                    f"{item.get('amount', 0):,.2f}"
                ]
                table_data.append(row)
            
            col_widths = [40, 70, 120, 80, 40, 40, 50, 80, 80]
            
            items_table = Table(table_data, colWidths=col_widths)
            items_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'MicrosoftYaHei' if 'MicrosoftYaHei' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('SPAN', (0, 0), (-1, 0)),
                ('FONTNAME', (0, 0), (-1, 0), 'MicrosoftYaHeiBold' if 'MicrosoftYaHeiBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10)
            ]))
            
            elements.append(items_table)
        else:
            elements.append(Paragraph("暂无报价项", normal_style))
        
        elements.append(Spacer(1, 20))
        
        summary = quotation_data.get("summary", {})
        
        summary_data = [
            ["项目", "金额"],
            ["小计", f"¥{summary.get('subtotal', 0):,.2f}"],
            ["运费", f"¥{summary.get('shipping', 0):,.2f}"],
            ["服务费", f"¥{summary.get('service_fee', 0):,.2f}"],
            ["折扣", f"-¥{summary.get('discount', 0):,.2f}"],
            ["税费", f"¥{summary.get('tax', 0):,.2f}"],
            ["", ""],
            ["总计", f"¥{summary.get('grand_total', 0):,.2f}"]
        ]
        
        summary_table = Table(summary_data, colWidths=[100, 150])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'MicrosoftYaHei' if 'MicrosoftYaHei' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 7), (1, 7), 'MicrosoftYaHeiBold' if 'MicrosoftYaHeiBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'),
            ('FONTSIZE', (0, 7), (1, 7), 12),
            ('BACKGROUND', (0, 7), (1, 7), colors.lightblue)
        ]))
        
        elements.append(Paragraph("金额汇总:", header_style))
        elements.append(Spacer(1, 10))
        elements.append(summary_table)
        
        elements.append(Spacer(1, 30))
        
        footer_style = ParagraphStyle(
            'Footer',
            fontName='MicrosoftYaHei' if 'MicrosoftYaHei' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
            fontSize=8,
            alignment=1,
            spaceAfter=5
        )
        
        elements.append(Paragraph("澄天生物科技有限公司", footer_style))
        elements.append(Paragraph("Cheng Tian Biotechnology Co., Ltd.", footer_style))
        
        doc.build(elements)
        
        buffer.seek(0)
        
        return buffer

    def _get_customer_type_label(self, customer_type: str) -> str:
        type_map = {
            "commercial": "Commercial",
            "npo": "NPO",
            "ka": "KA"
        }
        return type_map.get(customer_type, customer_type)

    def export_to_file(self, quotation_data: Dict, file_path: str) -> str:
        buffer = self.export_quotation(quotation_data)
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'wb') as f:
            f.write(buffer.getvalue())
        
        return file_path