import os
import logging
import json

from datapackage_pipelines.wrapper import process

from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError, OperationalError

TK = 'tender_key'
DISALLOWED = {'9999', '99999', '999999', '000000', '00000', '0000', '1111', 'TEST'}
db_table = 'procurement_tenders'
connection_string = os.environ['DPP_DB_ENGINE']
engine = create_engine(connection_string)

key_fields = ('publication_id', 'tender_type', 'tender_id')
to_select = ','.join(key_fields)

all_tenders = set()
for result in engine.execute(f'select {to_select} from {db_table}'):
    all_tenders.add(tuple(str(result[k]).strip() for k in key_fields))
all_tenders_dict = dict(
    [(t[0], t) for t in all_tenders if t[0] and len(t[0]) > 4] +
    [(t[2], t) for t in all_tenders if t[2] and len(t[2]) > 4 and t[2] != 'none']
)

logging.info('Collected %d tenders and exemptions', len(all_tenders))

def modify_datapackage(dp, *_):
    dp['resources'][0]['schema']['fields'].append(dict(
        name = TK,
        type = 'string'
    ))
    return dp

failed = set()
def process_row(row, *_):
    if TK in row:
        del row[TK]
    mf = row['manof_ref']
    if mf:
        mf = mf.strip()
    if mf and len(mf)>4:
        if mf not in failed:
            if mf not in DISALLOWED:
                if mf in all_tenders_dict:
                    row[TK] = json.dumps(list(all_tenders_dict[mf]))
                else:
                    for k, v in all_tenders_dict.items():
                        if k in mf:
                            row[TK] = json.dumps(list(v))
                            break
            if TK not in row:
                row[TK] = None
                logging.info('Failed to find reference for "%s"', mf)
                failed.add(mf)
        else:
            row[TK] = None
    else:
        row[TK] = None
    return row

if __name__ == '__main__':
    process(modify_datapackage=modify_datapackage,
            process_row=process_row)
