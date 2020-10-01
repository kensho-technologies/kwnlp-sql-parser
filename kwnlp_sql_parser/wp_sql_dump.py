"""Module for parsing Wikipedia SQL dumps."""

import csv
import gzip
import logging
import os
import re
import sys
import time
from contextlib import contextmanager
from typing import Any, Dict, IO, Iterator, List, Match, Optional, Tuple

from kwnlp_sql_parser.wp_sql_patterns import (
    WikipediaSqlRow,
    return_columns_tuple,
    return_valid_table_names,
)

logger = logging.getLogger(__name__)


class WikipediaSqlCsvDialect(csv.Dialect):
    """Default dialect for CSV output.

    See the Python CSV docs for more info
    https://docs.python.org/3/library/csv.html#csv-fmt-params.
    """

    delimiter = ","
    doublequote = True
    escapechar = None
    lineterminator = "\r\n"
    quotechar = '"'
    quoting = csv.QUOTE_MINIMAL
    skipinitialspace = False
    strict = False


class WikipediaSqlDump:
    """Class for Wikipedia SQL table dump files.

    Represents a SQL dump file of the form,

      * :code:`WIKI-YYYYMMDD-TABLE_NAME.sql.gz`

    This class can handle compressed gz files or uncompressed sql files.

    Wikimedia provides documentation on the tables these dumps come from,

      * https://www.mediawiki.org/wiki/Manual:Category_table
      * https://www.mediawiki.org/wiki/Manual:Redirect_table
      * https://www.mediawiki.org/wiki/Manual:Page_props_table
      * https://www.mediawiki.org/wiki/Manual:Page_table
      * https://www.mediawiki.org/wiki/Manual:Categorylinks_table
      * https://www.mediawiki.org/wiki/Manual:Pagelinks_table

    Parameters
    ----------
    filename
      The wikipedia SQL dump file name
    keep_column_names
      names of columns to keep in CSV output. if None then keep all.
    allowlists
      maps column names to allowlists of column values.  if None then keep all.
    blocklists
      maps column names to blocklists of column values.  if None then keep all.
    """

    _VALID_TABLE_NAMES = return_valid_table_names()
    _FILE_PATTERN = re.compile(
        r"""
        (?P<basename>               # basename group
          (?P<wiki>[a-z]+)          # wikipedia language prefix
          -                         # literal hyphen
          (?P<yyyymmdd>\d{8})       # year/month/day (e.g. 20180720)
          -                         # literal hyphen
          (?P<table_name>[\w_]+)    # name of wikimedia table
        )                           # close basname group
        (?P<extension>\.sql(\.gz)?) # extension
        """,
        re.VERBOSE,
    )

    def __init__(
        self,
        filename: str,
        keep_column_names: Optional[Tuple[str, ...]] = None,
        allowlists: Optional[Dict[str, Tuple[str, ...]]] = None,
        blocklists: Optional[Dict[str, Tuple[str, ...]]] = None,
    ) -> None:

        self.filename = filename

        match_groupdict = self._get_regex_groupdict_from_filename(filename)
        self.wiki = match_groupdict["wiki"]
        self.yyyymmdd = match_groupdict["yyyymmdd"]
        self.compressed = match_groupdict["extension"] == ".sql.gz"
        self.basename = match_groupdict["basename"]
        self.table_name = match_groupdict["table_name"]
        if self.table_name not in self._VALID_TABLE_NAMES:
            raise NotImplementedError(f"table name {self.table_name} not implemented")

        self.sqlrow = WikipediaSqlRow(
            return_columns_tuple(self.table_name),
            keep_column_names=keep_column_names,
            allowlists=allowlists,
            blocklists=blocklists,
        )
        self.compiled_row_pattern = self.sqlrow.build_compiled_pattern()
        logger.info(self)

    def _get_regex_groupdict_from_filename(self, filename: str) -> Dict[str, str]:
        if not isinstance(filename, str):
            raise ValueError("filename must be a string")
        basename = os.path.basename(filename)
        match = re.match(self._FILE_PATTERN, basename)
        if match:
            return match.groupdict()
        else:
            raise ValueError(
                f"basename of filename {basename} does not match the required "
                'pattern "WIKI-YYYYMMDD-TABLE_NAME.sql{.gz}'
            )

    @contextmanager
    def _open_dump_file(self) -> Iterator[IO[Any]]:
        """Context manager that opens compressed/uncompressed dump files.

        It is important to open the file in binary mode even if it is
        not compressed. This allows us to handle decoding in one place.
        """
        if self.compressed:
            with gzip.open(self.filename, mode="rb") as fp:
                yield fp
        else:
            with open(self.filename, mode="rb") as fp:
                yield fp

    def iter_lines(self) -> Iterator[str]:
        """Generate lines from SQL dump file."""
        with self._open_dump_file() as fp:
            for linebytes in fp:
                yield linebytes.decode(encoding="utf-8", errors="ignore")

    def iter_matched_rows(self) -> Iterator[Tuple[int, int, Match]]:
        """Generate regex row matches from SQL dump file.

        Each yield statement includes a match as well as line_num and
        insert_into_num. line_num indicates the line number of the SQL
        dump file the match was on and insert_into_num indicates the
        insert_into statement the match was in.  Both are 1-based
        counters.
        """
        line_num = 0
        insert_into_num = 0
        for line in self.iter_lines():
            line_num += 1

            # we are only interested in lines that insert data
            if not line.startswith("INSERT INTO"):
                logger.debug("  skipping non INSERT row")
                continue
            else:
                insert_into_num += 1

            # iterate over regex matches (i.e. database rows) in this line
            for match in re.finditer(self.compiled_row_pattern, line):
                yield line_num, insert_into_num, match

    def get_csv_header(self) -> Tuple[str, ...]:
        """Return CSV header."""
        return self.sqlrow.keep_column_names

    def to_csv(
        self,
        outfile: Optional[str] = None,
        dialect: Optional[csv.Dialect] = None,
        max_lines: int = sys.maxsize,
        batch_size: int = 500_000,
    ) -> None:
        """Produce a CSV file from a SQL dump.

        Parameters
        ----------
        outfile
          CSV output file name
        dialect
          CSV output format. defaults to :py:class:`WikipediaSqlCsvDialect`
        max_lines
          maximum number of INSERT statements to parse
        batch_size
          number of rows to write to the CSV at one time


        Wikipedia MySQL dumps contain a series of SQL commands that populate a MySql
        database.  The bulk of the files are `INSERT` commands followed by several
        thousand values (for example)

        .. code:: sql

            INSERT INTO `pagelinks` VALUES (9773,0,'!',0),(15154,0,'!',0), ...
        """
        count_row_matches = 0
        count_written = 0
        count_skipped_bc_ab_lists = 0

        if outfile is None:
            outfile = f"{self.basename}.csv"
        if dialect is None:
            dialect = WikipediaSqlCsvDialect()

        logger.info(f"writing CSV to {outfile}")
        batch_matches = []  # type: List[Match]
        t_start = time.time()
        t_batch_start = time.time()

        with open(outfile, "w") as fp:

            csv_writer = csv.writer(fp, dialect=dialect)
            csv_writer.writerow(self.get_csv_header())

            # iterate over regex row matches
            # line_num indicates which line of the SQL dump we're on
            for line_num, insert_into_num, match in self.iter_matched_rows():

                # return early if we need to
                if insert_into_num > max_lines:
                    batch_rows = self.sqlrow.csv_rows_from_matches(batch_matches)
                    csv_writer.writerows(batch_rows)
                    return

                # collect matches
                count_row_matches += 1
                batch_matches.append(match)

                # write batch to disk
                if len(batch_matches) >= batch_size:

                    batch_rows = self.sqlrow.csv_rows_from_matches(batch_matches)
                    csv_writer.writerows(batch_rows)

                    count_written += len(batch_rows)
                    count_skipped_bc_ab_lists += len(batch_matches) - len(batch_rows)
                    batch_matches = []

                    t_batch_end = time.time()
                    t_batch_end - t_batch_start
                    dt_all = t_batch_end - t_start
                    rows_per_sec = count_row_matches / dt_all
                    logger.info(
                        f"  time elapsed: {dt_all:.2f}s, "
                        f"  rows matched per second: {rows_per_sec:.2f}, "
                        f"  rows matched: {count_row_matches}, "
                        f"  rows written to disk: {count_written}, "
                        f"  rows skipped b/c allow/block lists: {count_skipped_bc_ab_lists}"
                    )
                    t_batch_start = time.time()

            # write any lingering rows
            batch_rows = self.sqlrow.csv_rows_from_matches(batch_matches)
            csv_writer.writerows(batch_rows)

    def __str__(self) -> str:
        return (
            f"{self.__class__}("
            f"filename={self.filename}, "
            f"yyyymmdd={self.yyyymmdd}, "
            f"compressed={self.compressed}, "
            f"basename={self.basename}, "
            f"table_name={self.table_name}, "
            f"sqlrow={self.sqlrow})"
        )

    def __repr__(self) -> str:
        return self.__str__()
