import math
import pandas as pd 
import numpy as np 
import ast

# Wczytanie danych
kredyty = pd.read_csv('tmdb_5000_credits.csv')
filmy = pd.read_csv('tmdb_5000_movies.csv')


# laczenie kolumn po ID - jedna tabela ma id a druga movie id wiec zmiana
filmy = filmy.rename(columns={'id': 'movie_id'})
df = filmy.merge(kredyty, on='movie_id')

kolumny_do_projektu = [
    'movie_id', 'title_x', 'cast', 'crew', 'genres', 'keywords', 
    'production_companies', 'budget', 'popularity', 'release_date', 
    'vote_average', 'vote_count'
]
df = df[kolumny_do_projektu]
df = df.rename(columns={'title_x': 'title'})


# --- FUNKCJE POMOCNICZE DO TEKSTOW ---

def wyciagnij_nazwy(tekst):
    if type(tekst) != str: 
        return []
    
    lista_elementow = ast.literal_eval(tekst)
    wynik = []
    
    for element in lista_elementow:
        nazwa = element['name']
        wynik.append(nazwa)
        
    return wynik


def wyciagnij_top3_aktorow(tekst):
    if type(tekst) != str: 
        return []
        
    lista_elementow = ast.literal_eval(tekst)
    wynik = []
    licznik = 0
    
    for element in lista_elementow:
        if licznik < 3:
            nazwa = element['name']
            wynik.append(nazwa)
            licznik += 1
        else:
            break
            
    return wynik


def wyciagnij_rezysera(tekst):
    if type(tekst) != str: 
        return []
        
    lista_elementow = ast.literal_eval(tekst)
    
    for element in lista_elementow:
        if element['job'] == 'Director':
            nazwa = element['name']
            return [nazwa]            
    return []


def usun_spacje(lista):
    return [element.replace(" ", "") for element in lista]


# --- WLACZANIE FUNKCJI NA KOLUMNY ---

df['genres'] = df['genres'].apply(wyciagnij_nazwy)
df['keywords'] = df['keywords'].apply(wyciagnij_nazwy)
df['production_companies'] = df['production_companies'].apply(wyciagnij_nazwy)
df['cast'] = df['cast'].apply(wyciagnij_top3_aktorow)
df['crew'] = df['crew'].apply(wyciagnij_rezysera)


dla_kolumn_tekstowych = ['genres', 'keywords', 'production_companies', 'cast', 'crew']
for kolumna in dla_kolumn_tekstowych:
    df[kolumna] = df[kolumna].apply(usun_spacje)


df['release_date'] = pd.to_datetime(df['release_date'], errors='coerce').dt.year    #data na rok 
df['release_date'] = df['release_date'].fillna(0).astype(int)                       # brak na 0


#    DEBUG  print(df.head(3))



# =============== Przygotowanie zmiennych

# min i max zmiennych by obliczac odleglosc a nie COS-similarity
max_budzet = df['budget'].max()
min_budzet = df['budget'].min()

max_rok = df['release_date'].max()
min_rok = df['release_date'].min()


# ================= Funkcje do obliczania podobienstwa 

def cosinus_dla_list(lista_a, lista_b):
    # Zabezpieczenie od pustych list
    if not lista_a or not lista_b:
        return 0.0
        
    # Zamieniamy listy na sety by latwo znalezc podobienstwo
    zbior_a = set(lista_a)
    zbior_b = set(lista_b)

    czesc_wspolna = len(zbior_a.intersection(zbior_b))
    mianownik = math.sqrt(len(zbior_a)) * math.sqrt(len(zbior_b))
    
    return czesc_wspolna / mianownik

def podobienstwo_liczbowe(wartosc_a, wartosc_b, wart_min, wart_max):
    if wart_max == wart_min:
        return 1.0
        
    # roznica miedzy min a max
    roznica = abs(wartosc_a - wartosc_b)
    #wzor na podobiestwo od 0 do 1
    return 1.0 - (roznica / (wart_max - wart_min))



def polec_filmy(id_filmu, df, ile_polecic=5):
    #czy ID jest w bazie
    if id_filmu not in df['movie_id'].values:
        return "Błąd: Nie znaleziono filmu o podanym ID."

    film_docelowy = df[df['movie_id'] == id_filmu].iloc[0]
    
    wyniki_podobienstwa = []

    # Petla szukania podobnych filmow 
    for rzad in df.itertuples():        #dziwna architektura pandy wymaga iterowania po tuplach
        if rzad.movie_id == id_filmu:    
            continue

        # podobienstwa kazdej z kategorii
        
        pod_gatunki = cosinus_dla_list(film_docelowy['genres'], rzad.genres)
        pod_slowa = cosinus_dla_list(film_docelowy['keywords'], rzad.keywords)
        pod_studio = cosinus_dla_list(film_docelowy['production_companies'], rzad.production_companies)
        pod_aktorzy = cosinus_dla_list(film_docelowy['cast'], rzad.cast)
        pod_rezyser = cosinus_dla_list(film_docelowy['crew'], rzad.crew)

        # podobienstwa liczbowe
        pod_budzet = podobienstwo_liczbowe(film_docelowy['budget'], rzad.budget, min_budzet, max_budzet)
        pod_rok = podobienstwo_liczbowe(film_docelowy['release_date'], rzad.release_date, min_rok, max_rok)


        #fajnie byloby zrobic by filmy z jednej serii (np. Harry potter 1,2,3 itd.) byly polecane bardziej niz po samym podobienstwu, 
        #dac je w listy i sprawdzac czy sa one w tej samej liscie czy cos 
        # --- Waga podobienstw      
        wynik_koncowy = (
            (0.30 * pod_gatunki) +
            (0.20 * pod_slowa) +
            (0.10 * pod_aktorzy) +
            (0.10 * pod_rezyser) +
            (0.10 * pod_studio) +
            (0.15 * pod_rok) +
            (0.05 * pod_budzet)
        )

        # --- Filtr przez oceny   ---
        if rzad.vote_count > 100:
            wynik_koncowy = wynik_koncowy * (rzad.vote_average / 10.0)
        else:
            wynik_koncowy = wynik_koncowy * 0.5

        # Zapisujemy tytul i wynik
        wyniki_podobienstwa.append((rzad.title, wynik_koncowy, rzad.vote_average))

    # Sort listy malejąco (indeks 1 w krotce)
    wyniki_podobienstwa.sort(key=lambda x: x[1], reverse=True)

    
    #Print tabeli
    print(f"\nPonieważ obejrzałeś '{film_docelowy['title']}', polecamy:\n")
    print(f"{'#':<5} | {'Tytuł filmu':<65} | {'Dopasowanie':<15} | {'Ocena widzów':<15}")
    print("-" * 110)

    #Filmy 
    for i, (tytul, wynik, ocena) in enumerate(wyniki_podobienstwa[:ile_polecic], 1):
        print(f"{i:<5} | {tytul:<65} | {wynik:<15.3f} | {ocena:<15}")


# --- TESTOWANIE ALGORYTMU ---

#polec_filmy(285, df, ile_polecic=10) #piraci z karaibow

#polec_filmy(680, df, ile_polecic=10) #pulp fiction

polec_filmy(10327, df, ile_polecic=10) #legalna blondynka
