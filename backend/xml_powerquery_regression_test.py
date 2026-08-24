from pathlib import Path
import tempfile

from app.models.schemas import SourceMapping
from app.services.data_profiler import _read_sample
from app.translators.m_generator import generate_m_query


def main():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "territories.xml"
        p.write_text('''<?xml version="1.0" encoding="utf-8"?>
<root><territories>
  <territory id="1"><Region>North</Region><Country>UK</Country><Amount>10</Amount></territory>
  <territory id="2"><Region>South</Region><Country>FR</Country><Amount>20</Amount></territory>
</territories></root>''', encoding='utf-8')
        df = _read_sample(p, 'XML')
        assert 'Region' in df.columns, df.columns
        assert 'Country' in df.columns, df.columns

        m = SourceMapping(
            source_id='x1', datasource='Territory', original_connection_type='xml',
            detected_source_path='territories.xml', target_connector='XML',
            target_file_path='territories.xml', table_name='Territory'
        )
        q = generate_m_query('Territory', m, None, expected_columns=[
            {'source_name':'Region','data_type':'Text'},
            {'source_name':'Country','data_type':'Text'},
            {'source_name':'Amount','data_type':'Decimal Number'},
        ])
        assert 'Xml.Tables(File.Contents' in q
        assert 'XML_ExpandAll' in q
        assert 'MissingField.UseNull' in q
        assert 'Expected_Columns = {"Region", "Country", "Amount"}' in q
        assert 'Table.SelectColumns(XML_CaseAligned, Expected_Columns, MissingField.UseNull)' in q
        print('XML Power Query regression: PASS')

if __name__ == '__main__':
    main()
