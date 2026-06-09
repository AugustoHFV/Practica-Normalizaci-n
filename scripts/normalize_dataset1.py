import pandas as pd
import os
from sqlalchemy import create_engine

DB_USER = os.getenv('DB_USER', 'myuser')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'mypassword')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'normalizacion')

engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

print("Leyendo dataset original...")
raw_data_path = 'data/raw/netflix_titles.csv'
df = pd.read_csv(raw_data_path)

df = df.fillna('Unknown') 

print("Iniciando proceso de normalización a 3FN...")

def extract_unique_entities(dataframe, column_name, entity_col_name):
    series = dataframe[column_name].str.split(', ').explode().str.strip()
    series = series[series != 'Unknown'].unique()

    entity_df = pd.DataFrame(series, columns=[entity_col_name])
    entity_df.insert(0, f'{entity_col_name}_id', range(1, len(entity_df) + 1))
    return entity_df

print("Generando tablas dimensionales...")
directors_df = extract_unique_entities(df, 'director', 'director_name')
cast_df = extract_unique_entities(df, 'cast', 'actor_name')
countries_df = extract_unique_entities(df, 'country', 'country_name')
genres_df = extract_unique_entities(df, 'listed_in', 'genre_name')

print("Generando tabla principal de títulos...")
titles_df = df[['show_id', 'type', 'title', 'date_added', 'release_year', 'rating', 'duration', 'description']].copy()

def create_junction_table(dataframe, main_id_col, entity_col, entity_df, entity_name):
    exploded = dataframe[[main_id_col, entity_col]].copy()
    exploded[entity_col] = exploded[entity_col].str.split(', ')
    exploded = exploded.explode(entity_col)
    exploded[entity_col] = exploded[entity_col].str.strip()
    merged = pd.merge(exploded, entity_df, left_on=entity_col, right_on=f'{entity_name}_name', how='inner')
    
    junction_df = merged[[main_id_col, f'{entity_name}_id']].drop_duplicates()
    return junction_df

print("Generando tablas de relación...")
title_director_df = create_junction_table(df, 'show_id', 'director', directors_df, 'director')
title_cast_df = create_junction_table(df, 'show_id', 'cast', cast_df, 'actor')
title_country_df = create_junction_table(df, 'show_id', 'country', countries_df, 'country')
title_genre_df = create_junction_table(df, 'show_id', 'listed_in', genres_df, 'genre')

os.makedirs('data/normalized/dataset1', exist_ok=True)

normalized_tables = {
    'directors': directors_df,
    'cast_members': cast_df,
    'countries': countries_df,
    'genres': genres_df,
    'titles': titles_df,
    'title_director': title_director_df,
    'title_cast': title_cast_df,
    'title_country': title_country_df,
    'title_genre': title_genre_df
}

print("Exportando a CSV y base de datos PostgreSQL...")
for table_name, dataframe in normalized_tables.items():
    csv_path = f'data/normalized/dataset1/{table_name}.csv'
    dataframe.to_csv(csv_path, index=False)

    try:
        dataframe.to_sql(table_name, engine, if_exists='replace', index=False)
        print(f" -> Tabla '{table_name}' exportada con éxito.")
    except Exception as e:
        print(f" -> Error al exportar la tabla '{table_name}' a BD: {e}")

print("\n¡Proceso de normalización automatizado completado con éxito!")