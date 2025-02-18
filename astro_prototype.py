import requests
from bs4 import BeautifulSoup
import re
from lxml import etree

# Function to convert MathML to text
def mathml_to_text(mathml):
    parser = etree.XMLParser(recover=True)
    tree = etree.fromstring(mathml, parser)
    return ''.join(tree.itertext())

# Loop through articles and save info in text files
def gather_info(article, headers):
    print(f"Gathering info on {article}")
    url = f'https://en.wikipedia.org/wiki/{article}'
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    if article == "Herbig_Ae/Be_star":
        output = open(f"info/Herbig_Ae_Be_star.txt", "w", encoding="utf-8")
    else:
        output = open(f"info/{article}.txt", "w", encoding="utf-8")
    pattern = re.compile(r'\[\d+\]') # Removes the citation numbers from the text

    # For now this only takes the text from the paragraphs, might add more in the future...
    for cell in soup.find_all('p'):
        if cell.text.strip() != "":
            # Handle MathML
            for math in cell.find_all('math'):
                math_text = mathml_to_text(str(math))
                math.replace_with(math_text)

            text = cell.get_text()
            text = re.sub(pattern, '', text)
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'\n+', '\n', text)
            output.write(text + "\n\n")
    
    output.close()
    print("Done!")

def main(): 
    headers={"User-Agent": "Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"}

    # These lists store the wiki articles
    topic_articles = ['Stellar_evolution', 'Stellar_classification', 'Hertzsprung–Russell_diagram', 'Light_curve', 'Stellar_kinematics',
                        'Luminosity', 'Cosmic_distance_ladder', 'Apparent_magnitude', 'Black-body_radiation', 'Black_body', 'Color_index',
                        'H_I_region', 'H_II_region', 'Molecular_cloud', 'Protostar', 'Herbig–Haro_object', 'T_Tauri_star', 'Herbig_Ae/Be_star', 
                        'Nebular_hypothesis', 'Brown_dwarf', 'Protoplanetary_disk', 'Debris_disk', 'Exoplanet', 'Gas_giant', 'Terrestrial_planet',
                        'Kepler%27s_laws_of_planetary_motion', 'Orbital_mechanics', 'Parallax']
    
    # PLEASE NOTE THAT THIS DOES NOT CONTAIN HH 7-11
    dso_articles = ['Orion_Nebula', 'Tarantula_Nebula', 'HD_80606_b', 'WASP-17b', 'WASP-121b', 'LTT_9779_b', 'GJ_1214_b', 'K2-18b', 'TOI-270',
                    'LHS_3844_b', 'PSR_B1257%2B12', 'WD_1856%2B534', '55_Cancri', 'Kepler-62', 'AU_Microscopii', 'Epsilon_Eridani', ]
    
    # Gathering text for both article groups and outputting to their respective files
    for article in topic_articles:
        gather_info(article, headers)
    for article in dso_articles:
        gather_info(article, headers)

main()