This repo contains the code to collect data from two sources. From IMDB, information about the titles can be retrieved such as the award, release dates and company credits. From Justwatch, streaming availability on different streaming platforms can be obtained, especially the newly added contents.

# Collect data from IMDB

## 1. Merge two IMDB public datasets to obtain all title IDs - tconst
First, download and save the following datasets to the desired working directory from [IMDB Non-Commercial Datasets](https://datasets.imdbws.com/): _title.episode.tsv.gz_ and _title.basics.tsv.gz_. The data contains information such as the release year, runtime and the unique ID of available titles. Details about the datasets can be found [here](https://developer.imdb.com/non-commercial-datasets/). The ID has the variable name _tconst_.  
  
Second, run the script `merge_imdb_dataset.py`. The output _imdb_merged.csv_ file is saved under the current working directory. It contains three columns: title ID (_tconst_), release year (for movies)/ start year (for series) (_title_yr_) and title name (_title_name_).

## 2. Navigate to and collect information from different pages
With the title IDs, we can build URLs and navigate to different pages. Sections [Award Collection](#award-sec) and [Details collection](#detail-sec) serve well for illustration purposes. The former collects the award winning and/or nomination info. The latter collects detailed info about release dates, production companies and distributors.\
The [Complete Workflow](#complete-workflow) section integrates all the steps and shows the entire workflow. 

### Collect the award wins & nominations <a name="award-sec"></a>
The script `scrape_award.py` collects award info of one title as an example. Two output files are saved under the _Award_ folder (will be created if not exists):
- _tconst_gen_YYYY-MM-DD.csv_: award name (e.g., BAFTA Awards), award ID and the number of the wins and/or nominations under each award.
- _tconst_YYYY-MM-DD.csv_: award name, nomination (or win) (e.g., 2020 Nominee), category (e.g., Best Writer), person, person ID, note and note ID (if any, e.g., for which episode or tie). Only saved when there is award record. 

### Collect release dates and company credits <a name="detail-sec"></a>
The script `scrape_award.py` collects detailed info of one title as an example. Two output files are saved under the _Company Credit_ folder (will be created if not exists):
- _tconst_distribution_YYYY-MM-DD.csv_: distributor (e.g., One Gate Media), company ID, the country and year (e.g., Germany, 2023) and note (type of distribution, e.g., DVD).
- _tconst_pro_YYYY-MM-DD.csv_: production company, company ID and the responsibility (e.g., pre-production software).
One output file is saved under the _Release_ folder (will be created if not exists):
- _tconst_release_YYYY-MM-DD.csv_: country of the release, date and location.

### Complete Workflow
The script `scrape_imdb_titles.py` performs a semi-automated process. First, check the main pages whether titles have streaming options. If not, the titles are skipped. If yes, collect relevant info on the main page such as the box office and metascore. \
Second, for titles available for streaming, collect and save the award info, release info and company credits from the corresponding pages. The funcs are in parallel using `concurrent.futures.ThreadPoolExecutor`.

# Collect data from Justwatch
The script `scrape_justwatch.py` first collects all the URLs of streaming platforms and saves an output file under the _New_Content_ folder (will be created if not exists). The output file is _justwatch_href_YYYY-MM-DD.csv_. The update frequency can be adjusted. The current value is 30 days. \
Second, using the URLs retrieved in the most recent file from the step above, the newly added contents on each platform are collected. The output file is _platform_YYYY-MM-DD.csv_: date when the content is added and href. 


> [!NOTE]
> All the scripts are adjusted to illustrate. For example, the script `scrape_imdb_titles.py` filters titles that are recent (released in or later than 2024) and stops once there is any title in the batch with streaming options. The script `scrape_justwatch.py` collects the updated titles of two platforms.
