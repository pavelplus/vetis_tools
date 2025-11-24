import os
import time
from datetime import datetime
from copy import copy

from openpyxl import load_workbook
from openpyxl.utils import range_boundaries, get_column_letter

from vetis_api.models import *


STORAGE_DIR = 'main/xls'


def stock_entries_to_xls(enterprise: Enterprise) -> str | None:

    delete_old_files(STORAGE_DIR)

    stock_entries = StockEntry.objects.filter(enterprise=enterprise, is_last=True, is_active=True).select_related('main', 'product_item', 'unit').order_by('date_expiry', '-entry_number')[:10]

    wb = load_workbook(filename=f'{STORAGE_DIR}/stock_template.xlsx')

    ws = wb['data']
    table = ws.tables['stock_entries']

    (col_s, row_s, col_e, row_e) = range_boundaries(table.ref)

    first_row_idx = row_s + table.headerRowCount # skip header row(s)

    current_row_idx = row_e + 1

    # s, ХС
    # s, Предприятие
    # s, Номер записи
    # d, Дата поступления
    # s, Статус
    # s, Наименование продукции
    # s, ЕИ
    # n, Объем
    # n, Остаток
    # s, Выработано
    # s, Годен до
    # d, Срок годности
    # s, Источник
    # s, Группа
    # s, Тип продукции

    for stock_entry in stock_entries:
        new_row = [
            str(stock_entry.enterprise.business_entity),
            str(stock_entry.enterprise),
            str(stock_entry.entry_number),
            stock_entry.main.date_created.date(),
            stock_entry.main.get_initial_status_display(),
            stock_entry.product_item_name,
            str(stock_entry.unit),
            stock_entry.main.initial_volume,
            stock_entry.volume,
            stock_entry.date_produced_display,
            stock_entry.date_expiry_display,
            stock_entry.date_expiry.astimezone(tz=TZ_MOSCOW).date(),
            stock_entry.main.source_ent_name,
            stock_entry.product_item.assort_group.name,
            stock_entry.get_product_type_display()
        ]

        ws.append(new_row)

        for target_cell, source_cell in zip(ws[current_row_idx], ws[first_row_idx]):
            target_cell.number_format = copy(source_cell.number_format)
        
        current_row_idx += 1

    current_row_idx -= 1

    table.ref = f'{get_column_letter(col_s)}{row_s}:{get_column_letter(col_e)}{current_row_idx}'

    filename = f'stock_entries_{datetime.now(tz=TZ_MOSCOW).strftime('%y%m%d_%H%M%S')}.xlsx'

    fullpath = f'{STORAGE_DIR}/{filename}'

    wb.save(fullpath)

    return fullpath


def delete_old_files(folder_path: str, hours: int = 1) -> int:
    if not os.path.exists(folder_path):
        return 0
    
    cutoff_time = time.time() - (hours * 60 * 60)

    to_delete = []

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        print(file_path)
        
        if os.path.isfile(file_path):
            
            file_mtime = os.path.getmtime(file_path)
            
            if file_mtime < cutoff_time:
                to_delete.append((filename, file_path, file_mtime))
    
    deleted_count = 0
    for filename, file_path, _ in to_delete:
        try:
            os.remove(file_path)
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting {filename}: {e}")
    
    return deleted_count
