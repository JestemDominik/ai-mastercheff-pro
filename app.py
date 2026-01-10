import os
import streamlit as st
from openai import OpenAI
import base64

# --- KONFIGURACJA ---
st.set_page_config(page_title="AI MasterCheff Pro", page_icon="👨‍🍳", layout="wide")

# Inicjalizacja klienta OpenAI (będzie użyta później)
# Funkcja pomocnicza do kodowania obrazu na base64 (wymagane przez API OpenAI)
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

# --- LOGIKA AI ---

def analyze_fridge_image(client, image_base64):
    """Analizuje zdjęcie lodówki i zwraca listę produktów."""
    response = client.chat.completions.create(
        model="gpt-4o", # Model widzący
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Wypisz po przecinku tylko jadalne produkty, które widzisz na tym zdjęciu. Nie dodawaj żadnego innego tekstu."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ],
            }
        ],
        max_completion_tokens=300,
    )
    return response.choices[0].message.content

def generate_recipe_logic(client, instruction, image_base64=None):
    """Główna logika generowania przepisu (tekst lub z obrazka potrawy)."""
    messages = [
        {"role": "system", "content": "Jesteś dietetykiem i szefem kuchni. Twoje przepisy muszą być bezpieczne, smaczne i zawierać makroskładniki."},
        {"role": "user", "content": []}
    ]
    
    # Dodajemy instrukcję tekstową
    messages[1]["content"].append({"type": "text", "text": instruction})
    
    # Jeśli jest zdjęcie (dla funkcji 'Odtwórz to danie'), dodajemy je
    if image_base64:
        messages[1]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}})

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=messages
    )
    return response.choices[0].message.content

def generate_dish_image(client, recipe_title):
    """Generuje wizualizację potrawy za pomocą DALL-E 3."""
    response = client.images.generate(
        model="dall-e-3",
        prompt=f"Profesjonalna fotografia kulinarna: {recipe_title}. Piękne oświetlenie, wysoka rozdzielczość, apetyczne.",
        size="1024x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url

# --- INTERFEJS UŻYTKOWNIKA ---

st.title("👨‍🍳 AI MasterCheff Pro")
st.markdown("Twój osobisty kucharz, dietetyk i fotograf w jednym.")


client = OpenAI(api_key="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")

# Zakładki funkcjonalności
tab1, tab2 = st.tabs(["📸 Skaner Lodówki & Gotowanie", "🕵️ Odtwórz to Danie"])

# --- ZAKŁADKA 1: SKANER LODÓWKI ---
with tab1:
    col1, col2 = st.columns([1, 1])
    
    # Obsługa stanu (Session State) dla listy składników
    if 'detected_ingredients' not in st.session_state:
        st.session_state.detected_ingredients = ""

    with col1:
        st.subheader("1. Co masz w kuchni?")
        
        # Opcja 1: Zdjęcie
        uploaded_fridge = st.file_uploader("Zrób/wgraj zdjęcie wnętrza lodówki", type=['jpg', 'png', 'jpeg'])
        if uploaded_fridge and st.button("🔍 Przeskanuj lodówkę"):
            with st.spinner("Analizuję zawartość lodówki..."):
                base64_image = encode_image(uploaded_fridge)
                detected = analyze_fridge_image(client, base64_image)
                st.session_state.detected_ingredients = detected
                st.success("Wykryto produkty!")

        # Opcja 2: Ręczna edycja (lub wpisanie od zera)
        ingredients = st.text_area(
            "Lista produktów (możesz edytować):", 
            value=st.session_state.detected_ingredients,
            height=150
        )
        health_filters = st.multiselect("Wybierz ograniczenia zdrowotne:", ["Cukrzyca (Niski IG)", "Nietolerancja laktozy", "Bezglutenowe", "IBS (Low FODMAP)", "Wegańskie"])
        people_count = st.number_input("Ile osób?", 1, 10, 2)
        mode = st.radio("Tryb:", ("Tylko z tego co mam", "Doradź co dokupić"))

    with col2:
        st.subheader("2. Twój Przepis")
        if st.button("🍲 Generuj Przepis + Makro"):
            if not ingredients:
                st.error("Lista produktów jest pusta!")
            else:
                with st.spinner("Szef kuchni układa menu i liczy kalorie..."):
                    # Budowanie promptu
                    safety_instruction = f"Użytkownik ma następujące ograniczenia: {', '.join(health_filters)}. Jeśli składniki są szkodliwe, zaproponuj bezpieczne zamienniki i wyjaśnij dlaczego." if health_filters else ""
                    
                    buy_instruction = "Możesz zasugerować 2-3 kluczowe składniki do dokupienia." if mode == "Doradź co dokupić" else "Używaj TYLKO podanych składników (plus sól/pieprz/olej)."
                    
                    full_prompt = (
                        f"Stwórz przepis dla {people_count} osób z: {ingredients}. {buy_instruction} "
                        f"{safety_instruction} "
                        "Wymagany format odpowiedzi: "
                        "1. Nazwa Dania. "
                        "2. Składniki (z zamiennikami jeśli dotyczy filtrów). "
                        "3. Instrukcja krok po kroku. "
                        "4. Sekcja 'Makro na porcję': Kalorie, Białko, Tłuszcze, Węglowodany (szacunkowo)."
                    )
                    
                    # Generowanie tekstu
                    recipe_content = generate_recipe_logic(client, full_prompt)
                    st.markdown(recipe_content)
                    
                    # Generowanie obrazka
                    st.markdown("---")
                    with st.spinner("Rysuję wizualizację potrawy..."):
                        # Wyciągamy pierwszą linię jako tytuł do promptu dla DALL-E
                        recipe_title = recipe_content.split('\n')[0]
                        image_url = generate_dish_image(client, recipe_title)
                        st.image(image_url, caption="Wizualizacja AI - Tak to może wyglądać!")

# --- ZAKŁADKA 2: ODTWÓRZ DANIE ---
with tab2:
    st.subheader("Reverse Engineering Smaku")
    st.write("Zjadłeś coś pysznego? Wgraj zdjęcie, a ja spróbuję zgadnąć przepis.")
    
    dish_photo = st.file_uploader("Zdjęcie potrawy z restauracji", type=['jpg', 'png', 'jpeg'], key="dish_uploader")
    
    if dish_photo and st.button("🕵️ Rozszyfruj przepis"):
        with st.spinner("Analizuję teksturę, składniki i styl dania..."):
            base64_dish = encode_image(dish_photo)
            
            prompt = (
                "Przeanalizuj to zdjęcie potrawy. Spróbuj dokonać inżynierii wstecznej (reverse engineering) przepisu. "
                "Zgadnij składniki, sposób obróbki i przyprawy na podstawie wyglądu i tekstury. "
                "Podaj przepis, który pozwoli uzyskać taki sam efekt w domu."
                "Na końcu podaj szacunkowe makroskładniki."
            )
            
            if health_filters:
                prompt += f" UWAGA: Użytkownik ma filtry: {', '.join(health_filters)}. Zaznacz, które elementy oryginału mogą być szkodliwe i podaj bezpieczną alternatywę, aby odtworzyć smak."

            result = generate_recipe_logic(client, prompt, image_base64=base64_dish)
            st.markdown(result)