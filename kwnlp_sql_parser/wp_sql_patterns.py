"""Regex patterns and classes for parsing Wikipedia SQL dumps."""

import re
from typing import Dict, FrozenSet, List, Match, Optional, Pattern, Tuple, Union

# Core regex patterns
# ---------------------------------------

# A string surrounded by single quotes that has backslash escaped text inside
# see https://stackoverflow.com/questions/430759/regex-for-managing-escaped-characters-for-items-like-string-literals
# for the theoretical underpinning
ESCAPED_STRING = re.compile(
    r"""
    '              # opening single quote
    [^'\\]*        # normal block = 0 or more characters that are not single quote or backslash
    (              # begin group for (escaped normal*)*
      \\.          # escaped anything
      [^'\\]*      # normal block
    )*             # end (escaped normal*)* group
    '              # closing single quote
    """,
    re.VERBOSE,
)

DIGIT = re.compile(
    r"""
    (-|\+)? # optional minus or plus sign
    \d      # integer
    """,
    re.VERBOSE,
)

DIGITS = re.compile(
    r"""
    (-|\+)? # optional minus or plus sign
    \d+     # 1 or more integers
    """,
    re.VERBOSE,
)

QUOTED_DIGITS = re.compile(
    r"""
    '       # opening single quote
    (-|\+)? # optional minus or plus sign
    \d+     # 1 or more integers
    '       # closing single quote
    """,
    re.VERBOSE,
)

FLOAT = re.compile(
    r"""
    (-|\+)? # optional minus or plus sign
    \d*     # 0 or more integers
    \.?     # optional period
    \d*     # 0 or more integers
    """,
    re.VERBOSE,
)

SINGLE_QUOTED_ANYTHING = re.compile(
    r"""
    '                                      # opening single quote
    .*?                                    # non greedy match anything
    '                                      # closing single quote
    """,
    re.VERBOSE,
)


# Custom column regex patterns
# ---------------------------------------
CL_TIMESTAMP = re.compile(
    r"""
    '                                      # opening single quiote
    \d{4}-\d{2}-\d{2}[ ]\d{2}:\d{2}:\d{2}  # yyyy-mm-dd hh:mm:ss pattern
    '                                      # closing single quote
    """,
    re.VERBOSE,
)

CL_TYPE = re.compile(
    r"""
    '                                      # opening single quote
    (page|subcat|file)                     # explicit values we accept
    '                                      # closing single quote
    """,
    re.VERBOSE,
)


class WikipediaSqlColumn:

    _SINGLE_QUOTE = "'"
    _DOUBLE_QUOTE = '"'
    _SINGLE_BACKSLASH = "\\"
    _DOUBLE_BACKSLASH = "\\\\"
    _BACKSLASH_SINGLE_QUOTE = "\\'"
    _BACKSLASH_DOUBLE_QUOTE = '\\"'

    def __init__(
        self,
        name: str,
        pattern: Pattern,
        nullable: bool = False,
        unquote: bool = False,
        unescape: bool = False,
    ):
        """Wikipedia SQL Column.

        Fixed description of a single column in one of the Wikipedia SQL dumps.

        Parameters
        ----------
        name
          the name of the column
        pattern
          a compiled regex pattern to match the column
        nullable
          True if the column allows NULL
        unquote
          True if we want to remove outer quotes before writing to CSV
        unescape
          True if we want to unescape before writing to CSV
        """
        self.name = name
        self.pattern = pattern
        self.nullable = nullable
        self.unquote = unquote
        self.unescape = unescape

    def build_pattern(self) -> str:
        """Return a regex with one named group equal to the column name."""
        if self.nullable:
            return "(?P<{}>NULL|({}))".format(self.name, self.pattern.pattern)
        else:
            return "(?P<{}>{})".format(self.name, self.pattern.pattern)

    def _unescape_string(self, string: str) -> str:
        """Remove backslash escape characters from a string."""
        s1 = string.replace(self._BACKSLASH_SINGLE_QUOTE, self._SINGLE_QUOTE)
        s2 = s1.replace(self._BACKSLASH_DOUBLE_QUOTE, self._DOUBLE_QUOTE)
        s3 = s2.replace(self._DOUBLE_BACKSLASH, self._SINGLE_BACKSLASH)
        return s3

    def _unquote_string(self, string: str) -> str:
        """Remove outer single quotes."""
        if string.startswith(self._SINGLE_QUOTE):
            string = string[1:]
        if string.endswith(self._SINGLE_QUOTE):
            string = string[:-1]
        return string

    def clean_string(self, string: str) -> str:
        """Optionally apply unquote and unescape functions to a string."""
        if self.nullable and string == "NULL":
            string = ""
        if self.unquote:
            string = self._unquote_string(string)
        if self.unescape:
            string = self._unescape_string(string)
        return string

    def __str__(self) -> str:
        return (
            f"{self.__class__}(name={self.name}, nullable={self.nullable}, "
            f"unquote={self.unquote}, unescape={self.unescape})"
        )

    def __repr__(self) -> str:
        return self.__str__()


class WikipediaSqlRow:
    def __init__(
        self,
        columns: Tuple[WikipediaSqlColumn, ...],
        keep_column_names: Optional[Tuple[str, ...]] = None,
        allowlists: Optional[Dict[str, Tuple[str, ...]]] = None,
        blocklists: Optional[Dict[str, Tuple[str, ...]]] = None,
    ):
        """Wikipedia SQL Row.

        Compose a series of column descriptions to create a row description.

        Parameters
        ----------
        columns
          all columns in the row
        keep_column_names
          names of columns to keep in CSV output. if None then keep all.
        allowlists
          maps column names to allowlists of column values.  if None then keep all.
        blocklists
          maps column names to blocklists of column values.  if None then keep all.
        """
        self.columns = columns
        self.all_column_names = tuple([col.name for col in self.columns])
        self.keep_column_names = self._get_keep_column_names(keep_column_names)
        self.keep_columns = tuple(
            [column for column in self.columns if column.name in self.keep_column_names]
        )
        self.allowlists = self._get_allowlists(allowlists)
        self.blocklists = self._get_blocklists(blocklists)

    def _get_keep_column_names(
        self, keep_column_names: Union[None, Tuple[str, ...]]
    ) -> Tuple[str, ...]:
        """Validate and reorder.

        Validate column names and put keep_column_names into
        all_column_names order.
        """
        if keep_column_names is None:
            return tuple(self.all_column_names)

        # check for duplicates in `keep_column_names`
        if len(keep_column_names) > len(set(keep_column_names)):
            raise ValueError(f"keep column names includes duplicates {keep_column_names}")

        # check for bad column names in `keep_column_names`
        bad_col_names = set(keep_column_names) - set(self.all_column_names)
        if len(bad_col_names) > 0:
            raise ValueError(
                f"keep column names includes {bad_col_names} which are not valid "
                f"column names for this table ({self.all_column_names})"
            )

        # put `keep_column_names` in the same order as `all_column_names`
        return tuple([name for name in self.all_column_names if name in keep_column_names])

    def _get_allowlists(
        self, allowlists: Union[None, Dict[str, Tuple[str, ...]]]
    ) -> Dict[str, FrozenSet[str]]:
        """Validate input and create sets of acceptable values."""
        if allowlists is None:
            return {}

        allowsets = {}
        for name, allowed in allowlists.items():
            if name not in self.all_column_names:
                raise ValueError(
                    f"column name {name} in allowlists is not a valid column "
                    f"name: {self.all_column_names}"
                )
            allowsets[name] = frozenset(allowed)
        return allowsets

    def _get_blocklists(
        self, blocklists: Union[None, Dict[str, Tuple[str, ...]]]
    ) -> Dict[str, FrozenSet[str]]:
        """Validate input and create sets of blocked values."""
        if blocklists is None:
            return {}

        blocksets = {}
        for name, blocked in blocklists.items():
            if name not in self.all_column_names:
                raise ValueError(
                    f"column name {name} in blocklists is not a valid column "
                    f"name: {self.all_column_names}"
                )
            blocksets[name] = frozenset(blocked)
        return blocksets

    def build_pattern(self) -> str:
        """Build row regex by joining column regex patterns."""
        rowpat = ",".join([column.build_pattern() for column in self.columns])
        rowpat = 4 * " " + rowpat  # for consistent indentation when printing
        rowpat = "\\(\n" + rowpat + "\n\\)"  # add opening ( and closing )
        return rowpat

    def build_compiled_pattern(self) -> Pattern:
        """Build compiled row regex."""
        return re.compile(self.build_pattern(), re.VERBOSE)

    def _clean_groupdict(self, groupdict: Dict[str, str]) -> Dict[str, str]:
        """Apply column specific cleaning to each match group."""
        return {column.name: column.clean_string(groupdict[column.name]) for column in self.columns}

    def _passes_allowlist_groupdict(self, groupdict: Dict[str, str]) -> bool:
        """Check groupdict against allowlists."""
        return all(
            [groupdict[column_name] in allowed for column_name, allowed in self.allowlists.items()]
        )

    def _passes_blocklist_groupdict(self, groupdict: Dict[str, str]) -> bool:
        """Check groupdict against blocklists."""
        return all(
            [
                groupdict[column_name] not in blocked
                for column_name, blocked in self.blocklists.items()
            ]
        )

    def _filter_groupdict(self, groupdict: Dict[str, str]) -> Dict[str, str]:
        """Remove columns we don't want to keep."""
        return {column_name: groupdict[column_name] for column_name in self.keep_column_names}

    def _csv_row_from_groupdict(self, groupdict: Dict[str, str]) -> Tuple[str, ...]:
        """Produce tuple in column order from groupdict."""
        return tuple([groupdict[column_name] for column_name in self.keep_column_names])

    def csv_rows_from_matches(self, matches: List[Match]) -> List[Tuple[str, ...]]:
        """Generate CSV row tuples from an iterable of match objects."""
        csv_rows = []
        for match in matches:
            match_groupdict = match.groupdict()
            clean_groupdict = self._clean_groupdict(match_groupdict)
            keep_row_allowlist = self._passes_allowlist_groupdict(clean_groupdict)
            keep_row_blocklist = self._passes_blocklist_groupdict(clean_groupdict)
            if keep_row_allowlist and keep_row_blocklist:
                filtered_groupdict = self._filter_groupdict(clean_groupdict)
                csv_rows.append(self._csv_row_from_groupdict(filtered_groupdict))
        return csv_rows

    def __str__(self) -> str:
        return (
            f"{self.__class__}("
            f"columns={self.columns}, "
            f"keep_column_names={self.keep_column_names}, "
            f"allowlists={self.allowlists}, "
            f"blocklists={self.blocklists})"
        )

    def __repr__(self) -> str:
        return self.__str__()


_TABLE_COLUMN_PATTERNS = {
    "category": (
        WikipediaSqlColumn("cat_id", DIGITS),
        WikipediaSqlColumn("cat_title", ESCAPED_STRING, unquote=True, unescape=True),
        WikipediaSqlColumn("cat_pages", DIGITS),
        WikipediaSqlColumn("cat_subcats", DIGITS),
        WikipediaSqlColumn("cat_files", DIGITS),
    ),
    "redirect": (
        WikipediaSqlColumn("rd_from", DIGITS),
        WikipediaSqlColumn("rd_namespace", DIGITS),
        WikipediaSqlColumn("rd_title", ESCAPED_STRING, unquote=True, unescape=True),
        WikipediaSqlColumn(
            "rd_interwiki", ESCAPED_STRING, nullable=True, unquote=True, unescape=True
        ),
        WikipediaSqlColumn(
            "rd_fragment", ESCAPED_STRING, nullable=True, unquote=True, unescape=True
        ),
    ),
    "page_props": (
        WikipediaSqlColumn("pp_page", DIGITS),
        WikipediaSqlColumn("pp_propname", SINGLE_QUOTED_ANYTHING, unquote=True),
        WikipediaSqlColumn("pp_value", ESCAPED_STRING, unquote=True, unescape=True),
        WikipediaSqlColumn("pp_sortkey", DIGITS, nullable=True),
    ),
    "page": (
        WikipediaSqlColumn("page_id", DIGITS),
        WikipediaSqlColumn("page_namespace", DIGITS),
        WikipediaSqlColumn("page_title", ESCAPED_STRING, unquote=True, unescape=True),
        WikipediaSqlColumn("page_restrictions", ESCAPED_STRING, unquote=True, unescape=True),
        WikipediaSqlColumn("page_is_redirect", DIGITS),
        WikipediaSqlColumn("page_is_new", DIGITS),
        WikipediaSqlColumn("page_random", FLOAT),
        WikipediaSqlColumn("page_touched", QUOTED_DIGITS, unquote=True),
        WikipediaSqlColumn("page_links_updated", QUOTED_DIGITS, nullable=True, unquote=True),
        WikipediaSqlColumn("page_latest", DIGITS),
        WikipediaSqlColumn("page_len", DIGITS),
        WikipediaSqlColumn(
            "page_content_model",
            ESCAPED_STRING,
            nullable=True,
            unquote=True,
            unescape=True,
        ),
        WikipediaSqlColumn("page_lang", ESCAPED_STRING, nullable=True, unquote=True, unescape=True),
    ),
    "categorylinks": (
        WikipediaSqlColumn("cl_from", DIGITS),
        WikipediaSqlColumn("cl_to", ESCAPED_STRING, unquote=True, unescape=True),
        WikipediaSqlColumn("cl_sortkey", SINGLE_QUOTED_ANYTHING),
        WikipediaSqlColumn("cl_timestamp", CL_TIMESTAMP, unquote=True),
        WikipediaSqlColumn("cl_sortkey_prefix", ESCAPED_STRING, unquote=True, unescape=True),
        WikipediaSqlColumn("cl_collation", ESCAPED_STRING, unquote=True, unescape=True),
        WikipediaSqlColumn("cl_type", CL_TYPE, unquote=True),
    ),
    "pagelinks": (
        WikipediaSqlColumn("pl_from", DIGITS),
        WikipediaSqlColumn("pl_namespace", DIGITS),
        WikipediaSqlColumn("pl_title", ESCAPED_STRING, unquote=True, unescape=True),
        WikipediaSqlColumn("pl_from_namespace", DIGITS),
    ),
}  # type: Dict[str, Tuple[WikipediaSqlColumn, ...]]


def return_valid_table_names() -> Tuple[str, ...]:
    """Get a tuple of valid table names."""
    return tuple(_TABLE_COLUMN_PATTERNS.keys())


def return_columns_tuple(table_name: str) -> Tuple[WikipediaSqlColumn, ...]:
    """Get a tuple of column patterns for a table."""
    return _TABLE_COLUMN_PATTERNS[table_name]
