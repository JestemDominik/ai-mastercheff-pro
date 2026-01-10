import os
import base64
import streamlit as st
from openai import OpenAI
import fal_client
import concurrent.futures

os.environ["FAL_KEY"] = st.secrets["FAL_KEY"]

st.set_page_config(page_title="AI MasterCheff Pro", page_icon="👨‍🍳", layout="wide")

def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

def analyze_fridge_image(client, image_base64):
    response = client.chat.completions.create(
        model="gpt-4o",
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

def generate_suggestions_logic(client, ingredients, diet, filters, mode, occasion, time):

    prompt = (
        f"Jesteś kreatywnym szefem kuchni. Bazując na składnikach: {ingredients}, "
        f"diecie: {diet} oraz wykluczeniach: {', '.join(filters)}, "
        f"zaproponuj 3 nazwy dań, które można z tego przygotować na {occasion} w czasie {time} minut"
        f"Tryb: {mode}. "
        "Wypisz TYLKO nazwy dań, oddzielone średnikiem (;). Nie dodawaj numeracji ani opisów."
    )
    
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content
    return [dish.strip() for dish in content.split(';') if dish.strip()]

def generate_full_recipe_logic(client, dish_name, ingredients, diet, filters, people_count, mode, occasion, time):
    safety_instruction = f"Użytkownik ma filtry: {', '.join(filters)}. Jeśli składniki są szkodliwe, użyj bezpiecznych zamienników." if filters else ""
    buy_instruction = "Możesz zasugerować składniki do dokupienia." if mode == "Doradź co dokupić" else "Staraj się używać głównie podanych składników."
    
    full_prompt = (
        f"Jesteś dietetykiem i kucharzem z pasją znającym się na lokalnej kuchni i gotującym pyszne dania. Przygotuj szczegółowy przepis na danie: '{dish_name}'. "
        f"Dieta: {diet}. Ilość osób: {people_count}. Ilość czasu na zrobienie {time} "
        f"Dostępne składniki: {ingredients}. {buy_instruction} {safety_instruction} "
        "Wymagany format odpowiedzi: "
        "1. Nazwa Dania (jako nagłówek). "
        "2. Krótki opis dlaczego to pasuje do diety. "
        "3. Lista Składników. "
        "4. Instrukcja krok po kroku. "
        "5. Makro na porcję (Kcal, B, T, W)."
    )

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": full_prompt}]
    )
    return response.choices[0].message.content

def generate_recipe_logic(client, instruction, image_base64=None):
    messages = [
        {"role": "system", "content": "Jesteś dietetykiem i szefem kuchni. Twoje przepisy muszą być bezpieczne, smaczne i zawierać makroskładniki."},
        {"role": "user", "content": []}
    ]
    
    messages[1]["content"].append({"type": "text", "text": instruction})
    
    if image_base64:
        messages[1]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    return response.choices[0].message.content

def generate_dish_image(recipe_title):
    prompt = f"Professional food photography of {recipe_title}. High resolution, delicious, 8k, close-up."
    
    try:
        result = fal_client.subscribe(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": prompt,
                "image_size": "square_hd",
                "num_inference_steps": 4,
                "enable_safety_checker": True
            },
            with_logs=True,
        )
        
        if result and "images" in result and len(result["images"]) > 0:
            return result["images"][0]["url"]
        
        return "https://via.placeholder.com/1024?text=Błąd+Generowania"

    except Exception as e:
        st.error(f"Błąd generowania obrazu: {str(e)}")
        return "https://via.placeholder.com/1024?text=ERROR"

# def generate_random(time, occasion):
    
#     full_prompt = (
#         f" Jesteś kucharzem z pasją. Przygotuj szczegółowy i przepis na {occasion}, zakładając że mam {time}, minut na gotowanie")

#     response = client.chat.completions.create(
#         model="gpt-5-mini",
#         messages=[{"role": "user", "content": full_prompt}]
#     )
#     return response.choices[0].message.content

st.title("👨‍🍳 AI MasterCheff Pro 2.0")
st.markdown("Twój osobisty kucharz - wybierz dietę, zobacz propozycje i gotuj!")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if 'detected_ingredients' not in st.session_state:
    st.session_state.detected_ingredients = ""
if 'dish_suggestions' not in st.session_state:
    st.session_state.dish_suggestions = []
if 'final_recipe' not in st.session_state:
    st.session_state.final_recipe = None
if 'final_image' not in st.session_state:
    st.session_state.final_image = None

tab1, tab2, tab3 = st.tabs(["📸 Skaner & Planer", "🕵️ Odtwórz Danie", "Zaskocz mnie!"])

with tab1:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("1. Konfiguracja")
        
        uploaded_fridge = st.file_uploader("Zdjęcie lodówki (opcjonalnie)", type=['jpg', 'png', 'jpeg'])
        if uploaded_fridge and st.button("🔍 Skanuj produkty"):
            with st.spinner("Analizuję zawartość..."):
                base64_image = encode_image(uploaded_fridge)
                detected = analyze_fridge_image(client, base64_image)
                st.session_state.detected_ingredients = detected
                st.success("Produkty wykryte!")

        ingredients = st.text_area(
            "Twoje składniki:", 
            value=st.session_state.detected_ingredients,
            height=100,
            placeholder="np. jajka, pomidory, ser, makaron..."
        )

        st.markdown("---")
        st.subheader("Preferencje")
        
        diet_type = st.selectbox(
            "Wybierz rodzaj diety:",
            ["Zbilansowana (Brak)", "Ketogeniczna (Keto)", "Wegańska", "Wegetariańska", "Paleo", "Wysokobiałkowa", "Śródziemnomorska"]
        )

        health_filters = st.multiselect("Wykluczenia zdrowotne:", ["Bezglutenowe", "Bez laktozy", "Cukrzyca (Niski IG)", "Lekkostrawne"])
        people_count = st.number_input("Ile osób?", 1, 10, 2)
        mode = st.radio("Tryb zakupów:", ("Tylko z tego co mam", "Doradź co dokupić"))
        occasion = st.selectbox('Jaka okazja?', ['Śniadanie', 'Obiad', 'Kolacja', 'Impreza', 'Przekąska'])
        time = st.slider("Ile masz minut?", 10, 120, 30)

        st.markdown("---")
        
        if st.button("💡 Zaproponuj 3 dania"):
            if not ingredients:
                st.warning("Wpisz składniki lub wgraj zdjęcie.")
            else:
                st.session_state.final_recipe = None 
                st.session_state.final_image = None
                
                with st.spinner("Generuję propozycje..."):
                    suggestions = generate_suggestions_logic(client, ingredients, diet_type, health_filters, mode, occasion, time)
                    st.session_state.dish_suggestions = suggestions

    with col2:
        st.header("2. Wybór i Przepis")

        if st.session_state.dish_suggestions:
            st.info(f"Propozycje dla diety: **{diet_type}**")
            
            b_col1, b_col2, b_col3 = st.columns(3)
            selected_dish = None

            for idx, dish in enumerate(st.session_state.dish_suggestions):
                target_col = [b_col1, b_col2, b_col3][idx % 3]
                with target_col:
                    if st.button(dish, key=f"btn_{idx}", use_container_width=True):
                        selected_dish = dish

            if selected_dish:
                st.info(f"👨‍🍳 Szef kuchni i fotograf pracują równocześnie nad: **{selected_dish}**...")
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future_recipe = executor.submit(
                        generate_full_recipe_logic, 
                        client, selected_dish, ingredients, diet_type, health_filters, people_count, mode
                    )
                    
                    future_image = executor.submit(
                        generate_dish_image, 
                        selected_dish
                    )
                    
                    recipe = future_recipe.result()
                    image_url = future_image.result()

                st.session_state.final_recipe = recipe
                st.session_state.final_image = image_url
                st.rerun()

        if st.session_state.final_recipe:
            st.markdown("---")
            st.success("Gotowe!")
            
            if st.session_state.final_image:
                st.image(st.session_state.final_image, caption="Wizualizacja AI")
            
            st.markdown(st.session_state.final_recipe)

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

