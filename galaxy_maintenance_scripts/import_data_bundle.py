import os
import tempfile
from typing import Optional

import click
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from galaxy.tool_util.data import BundleProcessingOptions
from galaxy.tools.data import ToolDataTableManager
from galaxy.util import requests


CHUNK_SIZE = 65536  # 64k


@click.command(help="Import tool data bundle. URI can be a path to a zipped file or directory.")
@click.option("--tool-data-path", type=click.Path(exists=True, resolve_path=True), help="Path were bundle data should be written to")
@click.option("--data-table-config-path", type=click.Path(exists=True, resolve_path=True), help="Path to tool_data_table_conf.xml file")
@click.option(
    "-t",
    "--tool-data-file-path",
    type=click.Path(exists=True, resolve_path=True),
    help="loc file to append data to. Must be be loaded in general data tables",
)
@click.option("--retry-backoff", type=float, default=1.0, help="Retry backoff")
@click.option("--retry-count", type=int, default=5, help="Number of times to retry http failures")
@click.argument("uri")
def run_import_data_bundle(
        uri: str,
        retry_count: int,
        retry_backoff: int,
        tool_data_path: str,
        data_table_config_path: str,
        tool_data_file_path: Optional[str] = None
    ):
    table_manager = ToolDataTableManager(
        tool_data_path=tool_data_path,
        config_filename=data_table_config_path,
    )
    options = BundleProcessingOptions(
        what="data import",  # An alternative to this is sticking this in the bundle, only used for logging.
        data_manager_path=tool_data_path,
        # I'll make this optional upstream
        target_config_file="unused",
        tool_data_file_path=tool_data_file_path,
    )
    if uri.startswith("file://"):
        target = uri[len("file://") :]
        table_manager.import_bundle(
            target,
            options,
        )
    else:
        session = requests.Session()
        retries = Retry(total=retry_count, backoff_factor=retry_backoff, status_forcelist=[500, 502, 503, 504])
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))
        with tempfile.NamedTemporaryFile(mode="wb") as fh, session.get(uri, stream=True) as r:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                fh.write(chunk)
            fh.flush()
            table_manager.import_bundle(
                fh.name,
                options,
            )


if __name__ == "__main__":
    run_import_data_bundle()
