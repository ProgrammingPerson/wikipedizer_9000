import requests
import time
from bs4 import BeautifulSoup

# A function that does exactly what its called
def export_data(info, output):
    file = open(output, "w", encoding="utf-8")
    
    for paragraph in info:
        file.write(paragraph + "\n\n")
    
    file.close()

# Loop through the articles provided and gathers the text
def gather_text(articles, headers, storage):
    for article in articles:
        print(f"Gathering info on {article}")
        url = f'https://en.wikipedia.org/wiki/{article}'

        response = requests.get(url, headers=headers)

        soup = BeautifulSoup(response.text, 'html.parser')

        # For now this only takes the text from the paragraphs, might add more in the future...
        for cell in soup.find_all('p'):
            storage.append(cell.text)

        print("Done!")

def main(): 
    headers={"User-Agent": "Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"}

    # These lists store the wiki articles
    topic_articles = ['Stellar_evolution', 'Stellar_classification', 'Hertzsprung–Russell_diagram', 'Light_curve', 'Stellar_kinematics', 'Luminosity', 'Cosmic_distance_ladder', 'Apparent_magnitude', 
                'Black-body_radiation', 'Black_body', 'Color_index', 'H_I_region', 'H_II_region', 'Molecular_cloud', 'Protostar', 'Herbig–Haro_object', 'T_Tauri_star', 'Herbig_Ae/Be_star', 
                'Nebular_hypothesis', 'Brown_dwarf', 'Protoplanetary_disk', 'Debris_disk', 'Exoplanet', 'Gas_giant', 'Terrestrial_planet', 'Kepler%27s_laws_of_planetary_motion', 
                'Orbital_mechanics', 'Parallax']
    
    # PLEASE NOTE THAT THIS DOES NOT CONTAIN HH 7-11
    dso_articles = ['Carina_Nebula', 'NGC_1333', 'TW_Hydrae', 'AB_Aurigae', 'HD_169142', 'Luhman_16', 'V830_Tauri', 
                    'V1298_Tauri', 'WASP-18b', 'WASP-39b', 'WASP-43b', 'HR_8799', 'Beta_Pictoris', '2M1207', 'TRAPPIST-1']

    # These store the text that is collected
    topic_paragraphs = []
    dso_paragraphs = []

    # Gathering text for both article groups and outputting to their respective files
    gather_text(topic_articles, headers, topic_paragraphs)
    export_data(topic_paragraphs, "astronomy.txt")

    gather_text(dso_articles, headers, dso_paragraphs)
    export_data(dso_paragraphs, "DSOs.txt")

main()