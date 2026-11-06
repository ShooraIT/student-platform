from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font


def build_workbook(sheets):
    """sheets: [(title, header, rows), ...]"""
    wb = Workbook()
    wb.remove(wb.active)
    for title, header, rows in sheets:
        ws = wb.create_sheet(title[:31])
        ws.append(header)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in rows:
            ws.append(list(r))
        for i, h in enumerate(header, start=1):
            width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows[:200] if i - 1 < len(r)]) + 2
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(width, 60)
    return wb


def workbook_response(filename, wb):
    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp


def xlsx_response(filename, title, header, rows):
    return workbook_response(filename, build_workbook([(title, header, list(rows))]))
