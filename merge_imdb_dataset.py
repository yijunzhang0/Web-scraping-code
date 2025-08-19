import pandas as pd

# The datasets can be downloaded from the IMDB website. 

### Merge datasets ###
# Since (1) for TV series, each episode has a title ID that is different from the main title (parentTconst) and 
# the specific page has no detailed infomation for the series such as the producer,
# (2) there are some episodes that have the same names as other series and movies,
# we need to merge datasets containing unique title ID, start (release) year, connection between series and episodes first.

episodes = pd.read_csv('title.episode.tsv.gz', sep='\t', usecols=['tconst','parentTconst'])
chunk_list = []
for chunk in pd.read_csv('title.basics.tsv.gz', sep='\t', usecols=['tconst','primaryTitle','startYear'], chunksize=10000):
    chunk = chunk.rename(columns={'primaryTitle':'title_name','startYear':'title_yr'}).merge(
        episodes, how='left', on='tconst')
    # if 'parentTconst' is NA, the title is a movie
    # if series, replace ID of episodes by that of parent series
    chunk['tconst'] = chunk['parentTconst'].fillna(chunk['tconst'])
    chunk.drop(columns=['parentTconst'], inplace=True)
    chunk_list.append(chunk)
    
imdb_df = pd.concat(chunk_list)
imdb_df.to_csv('imdb_merged.csv', index=False)
print(f'''\nIMDB dataset merged!\n''')