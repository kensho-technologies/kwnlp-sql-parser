# Kensho Wikimedia for Natural Language Processing - SQL Dump Parser

kwnlp_sql_parser is a Python package for parsing [Wikipedia SQL dumps](https://meta.wikimedia.org/wiki/Data_dumps/Dump_format) into CSVs.


# Quick Install (Requires Python >= 3.6)

```bash
pip install kwnlp-sql-parser
```

# Examples

## Basic Usage

To convert a Wikipedia MySQL/MariaDB dump into a CSV file, use the `to_csv` method of the `WikipediaSqlDump` class.  By default, the CSV file is created in the current directory and includes all of the columns and rows in the SQL dump file.

```python
import pandas as pd
from kwnlp_sql_parser import WikipediaSqlDump
file_path = "/path/to/data/enwiki-20200920-page.sql.gz"
wsd = WikipediaSqlDump(file_path)
wsd.to_csv()
```

```python
df = pd.read_csv("enwiki-20200920-page.csv", keep_default_na=False, na_values=[""])
print(df.head())
```

```bash
   page_id  page_namespace            page_title page_restrictions  page_is_redirect  page_is_new  page_random    page_touched  page_links_updated  page_latest  page_len page_content_model  page_lang
0       10               0   AccessibleComputing               NaN                 1            0     0.331671  20200903074851        2.020090e+13    854851586        94           wikitext        NaN
1       12               0             Anarchism               NaN                 0            0     0.786172  20200920023613        2.020092e+13    979267494     88697           wikitext        NaN
2       13               0    AfghanistanHistory               NaN                 1            0     0.062150  20200909184138        2.020091e+13    783865149        90           wikitext        NaN
3       14               0  AfghanistanGeography               NaN                 1            0     0.952234  20200915100945        2.020091e+13    783865160        92           wikitext        NaN
4       15               0     AfghanistanPeople               NaN                 1            0     0.574721  20200917080644        2.020091e+13    783865293        95           wikitext        NaN
```

See the "Common Issues" section below for an explanation of the pandas read_csv kwargs.


## Filtering Rows and Columns

In some situations, it is convenient to filter the Wikipedia SQL dumps before writing to CSV.  For example, one might only be interested in the columns `page_id` and `page_title` for Wikipedia pages that are in the (Main/Article) [namespace](https://en.wikipedia.org/wiki/Wikipedia:Namespace).

```python
import pandas as pd
from kwnlp_sql_parser import WikipediaSqlDump
file_path = "/path/to/data/enwiki-20200920-page.sql.gz"
wsd = WikipediaSqlDump(
    file_path,
    keep_column_names=["page_id", "page_title"],
    allowlists={"page_namespace": ["0"]})
wsd.to_csv()
```

```python
df = pd.read_csv("enwiki-20200920-page.csv", keep_default_na=False, na_values=[""])
print(df.head())
```

```bash
   page_id            page_title
0       10   AccessibleComputing
1       12             Anarchism
2       13    AfghanistanHistory
3       14  AfghanistanGeography
4       15     AfghanistanPeople
```

Note that you can also specify `blocklists` instead of `allowlists` if it is more convenient for your use case.

# Common Issues

### Not using string values in filters

All values in the allowlists and blocklists should be strings.

### Pages with names treated as Null

Be carefull when reading the CSVs in your chosen software. Some packages will treat the following page titles as null values instead of strings,

* https://en.wikipedia.org/wiki/NaN
* https://en.wikipedia.org/wiki/Null
* https://en.wikipedia.org/wiki/Na

In pandas this can be handled by reading in the CSV using,

```python
df = pd.read_csv("enwiki-20200920-page.csv", keep_default_na=False, na_values=[""])
```


# Supported Tables

* https://www.mediawiki.org/wiki/Manual:Category_table
* https://www.mediawiki.org/wiki/Manual:Categorylinks_table
* https://www.mediawiki.org/wiki/Manual:Page_table
* https://www.mediawiki.org/wiki/Manual:Page_props_table
* https://www.mediawiki.org/wiki/Manual:Pagelinks_table
* https://www.mediawiki.org/wiki/Manual:Redirect_table


# License

Licensed under the Apache 2.0 License. Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

Copyright 2020-present Kensho Technologies, LLC. The present date is determined by the timestamp of the most recent commit in the repository.
