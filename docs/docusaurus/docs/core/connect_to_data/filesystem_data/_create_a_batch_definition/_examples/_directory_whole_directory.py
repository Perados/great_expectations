# <snippet name="docs/docusaurus/docs/core/connect_to_data/filesystem_data/_create_a_batch_definition/_examples/_directory_whole_directory.py - full_example">
# <snippet name="docs/docusaurus/docs/core/connect_to_data/filesystem_data/_create_a_batch_definition/_examples/_directory_whole_directory.py - retrieve Data Asset">
from pathlib import Path

import great_expectations as gx

context = gx.get_context()

data_source_name = "my_filesystem_data_source"
data_asset_name = "my_directory_data_asset"
file_data_asset = context.data_sources.get(data_source_name).get_asset(data_asset_name)
# </snippet>

print("--- ci debug ----")
print(file_data_asset)
ds = context.data_sources.get(data_source_name)
print(ds)
expected_data_dir = ds.base_directory / file_data_asset.data_directory
print(f"does data source data_directory exist? {expected_data_dir}")
print(Path.exists(expected_data_dir))

# <snippet name="docs/docusaurus/docs/core/connect_to_data/filesystem_data/_create_a_batch_definition/_examples/_directory_whole_directory.py - add Batch Definition">
batch_definition_name = "yellow_tripdata"
batch_definition = file_data_asset.add_batch_definition_whole_directory(
    name=batch_definition_name
)
# </snippet>

# <snippet name="docs/docusaurus/docs/core/connect_to_data/filesystem_data/_create_a_batch_definition/_examples/_directory_whole_directory.py - retrieve and verify Batch">
batch = batch_definition.get_batch()
batch.head()
# </snippet>
# </snippet>
