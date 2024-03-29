import os

from selenium import webdriver
from selenium.common import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from flask_restful import Resource
from selenium.webdriver.common.keys import Keys
from basic_fuc import db_conn, query_insert, db_disconn, query_select

#유저가 검색하면 크롤링 후 DB에 저장하는 API
class recipeCrawlingAPI(Resource):
    def get(self):
        urllink = 'https://www.10000recipe.com/recipe/list.html'
        basic_setting(urllink)
        return "크롤링 작업이 성공적으로 실행되었습니다."

#크롤링할 url 설정 함수
def basic_setting(urllink):
    # 1.WebDriver객체 생성
    driver_path = f'{os.path.join(os.path.dirname(__file__), "chromedriver.exe")}'
    # 웹드라이버를 위한 Service객체 생성
    service = Service(executable_path=driver_path)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # headless 모드 설정
    # 자동종료 막기
    options.add_experimental_option("detach", True)
    driver = webdriver.Chrome(service=service, options=options)
    # 2.브라우저에 네이버 로그인페이지 로딩하기
    driver.get(urllink)  # form에 있는 액션 url
    time.sleep(2)  # 페이지가 완전히 로딩되도록 3초동안 기다림

    # 분류 - 상황별 - 다이어트(6)..
    Category = driver.find_element(By.XPATH, '//*[@id="id_search_category"]/table/tbody/tr[1]/td/div/div[2]/a[6]')
    category_text = Category.text
    print(f'카테고리 : {category_text}')
    Category.click()
    time.sleep(1)

    # 레시피 제목 가져오기
    recipes = driver.find_elements(By.XPATH, '//*[@id="contents_area_full"]/ul/ul/li[*]')
    get_recipe(driver, recipes, category_text)

#레시피 정보 가져오기
def get_recipe(driver, recipes, category_text):
    connection = db_conn()
    ind = 1

    for recipe in recipes:
        print(f'[{ind}]')
        time.sleep(3)
        div_tags = recipe.find_elements(By.XPATH, './div')

        # 링크,img + span유무에 따른 동영상 여부
        first_div = div_tags[0]
        first_in_a = first_div.find_element(By.TAG_NAME, 'a')

        # 레시피 링크
        href_value = first_in_a.get_attribute('href')

        # 제목,유저정보,조회수&별점
        second_div = div_tags[1]
        second_in_div = second_div.find_elements(By.XPATH, './div')
        recipe_title = second_in_div[0] #제목

        print(f'제목:{recipe_title.text}, 링크:{href_value}')
        recipeCode = href_value.rsplit("/", 1)[-1]
        print('레시피 코드:',recipeCode)

        # 이전 탭에서 가져온 recipe_title 값을 저장
        recipe_title_value = recipe_title.text
        # 현재 탭의 핸들 저장
        current_tab = driver.current_window_handle
        # 요리 상세보기 링크를 새로운 탭에서 열기
        first_in_a.send_keys(Keys.CONTROL + Keys.RETURN)
        # 새로 열린 탭으로 전환
        driver.switch_to.window(driver.window_handles[-1])
        wait = WebDriverWait(driver, 30)
        # URL에 recipeCode 값을 포함시켜 전달
        driver.get(f"{driver.current_url}?recipeCode={recipeCode}")

        # URL에서 recipeCode 값을 읽어옴
        url = driver.current_url
        recipeCode = url.split('=')[-1]
        time.sleep(3)

        # 레시피 정보 크롤링 -> 구조 변경으로 요리명 가져올 수가 없어서 코드제거 후 따로 전처리 작업 진행
        try:
            cooking_orders = []  # 조리 순서를 담을 리스트를 생성합니다.
            step_number = 1  # 초기 스텝 번호
            while True:
                xpath = '//*[@id="stepdescr{}"]'.format(step_number)
                try:
                    Cooking_order = driver.find_element(By.XPATH, xpath)
                    cooking_orders.append(Cooking_order.text.replace('\n', '-'))  # 조리 순서를 리스트에 추가
                    step_number += 1 # 다음 스텝으로 넘어가기 위해 스텝 번호를 증가
                except NoSuchElementException:
                    break
            recipe_seq_str = '|| '.join(cooking_orders)
            print(f'조리 순서 : {recipe_seq_str}')
            recipe_image = driver.find_element(By.XPATH,'//*[@id="main_thumbs"]').get_attribute('src')
            print(f'이미지 링크 : {recipe_image}')
            # DB에 해당 레시피가 존재하는지 확인 후, 존재하면 레시피 순서 업데이트, 존재하지 않으면 신규 등록
            select_query = "SELECT COUNT(*) FROM Recipe WHERE recipeCode = :recipeCode"
            select_result = query_select(connection, query=select_query, recipeCode=recipeCode)
            if select_result[0][0] == 0:
                recipe_url = f"https://www.10000recipe.com/recipe/{recipeCode}"
                insert_query = "INSERT INTO Recipe(recipeCode, recipe_url, recipe_title, recipe_img, recipe_seq) VALUES (:recipeCode, :recipe_url, :recipe_title, :recipe_img, :recipe_seq)"
                query_insert(connection, query=insert_query, recipeCode=recipeCode, recipe_url=recipe_url,
                             recipe_title=recipe_title_value, recipe_img=recipe_image, recipe_seq=recipe_seq_str)
            else:
                print("해당 레시피는 DB에 이미 존재하며, 레시피 순서를 보충하기 위해 업데이트 합니다.")
                update_query = "UPDATE Recipe SET recipe_seq = :recipe_seq WHERE recipeCode = :recipeCode"
                query_insert(connection, query=update_query, recipeCode=recipeCode, recipe_seq=recipe_seq_str)
                print("업데이트 완료")
        except TimeoutException:
            print("시간 내 요소를 못찾았습니다.")
            pass
        except NoSuchElementException:
            print("찾는 요소가 없습니다.")
            pass
        # 레시피 세부 재료 크롤링 함수 실행
        recipe_info(connection, driver, wait, current_tab, recipeCode)
        ind += 1
    db_disconn(connection)

#####################################################################
#레시피별 세부 정보 가져오기
def recipe_info(connection,driver, wait, current_tab, recipeCode):
    # 재료 정보 가져오기 (재료, 투입량, 구매 링크) -> 여기서 ul 개수를 체크할 필요가 있을 것 같음. (ul이 하나면 재료만 적힌 것. ul이 두개면 양념이나 다른 추가 정보도 존재..)
    jaros_atag = driver.find_elements(By.XPATH, '//*[@id="divConfirmedMaterialArea"]/ul[1]/a[*]')
    for jaro in jaros_atag:
        jaro_li = jaro.find_element(By.XPATH, './li').text
        ingredient = jaro_li.split('\n')[0]
        jaro_span = jaro.find_element(By.XPATH, './li/span')
        print(f'재료명 :{ingredient} - 투입량 : {jaro_span.text}')


        select_query = "SELECT COUNT(*) FROM Recipe_ingredients WHERE ingredient = :ingredient and recipeCode = :recipeCode"
        select_result = query_select(connection, query=select_query, ingredient=ingredient, recipeCode=recipeCode)
        if select_result[0][0] == 0:
            insert_query = "INSERT INTO Recipe_ingredients(ingredient, recipeCode, RI_amount) VALUES (:ingredient, :recipeCode, :RI_amount)"
            query_insert(connection, query=insert_query, ingredient=ingredient, recipeCode=recipeCode,
                      RI_amount=jaro_span.text)
        else:
            print("해당 재료가 이미 DB에 존재..")

        # #각종 광고 제거
        # delete_abs(driver,wait)
        # #재료별 상세 정보
        # ingredient_info(driver, wait, first_a_tag)

    # 새로운 탭 닫기
    driver.close()
    # 기존 탭으로 전환
    driver.switch_to.window(current_tab)



#재료의 상세정보
def ingredient_info(driver, wait, first_a_tag):
    first_a_tag.click()
    time.sleep(3)  # 모달 클릭 이후 정보를 동적정보를 가지고 오는동안 대기

    try:
        print('들어옴')
        # 재료 상세정보
        jaroinfos = driver.find_elements(By.XPATH, '//*[@id="materialBody"]/div/div[2]/table/tbody/tr[*]')
        print(jaroinfos)
        for jaroinfo in jaroinfos:
            jaroinfo_th = jaroinfo.find_element(By.XPATH, './th')
            jaroinfo_td = jaroinfo.find_element(By.XPATH, './td')
            print(f'{jaroinfo_th.text} - {jaroinfo_td.text}')
        wait.until(EC.presence_of_element_located(
            (By.XPATH, '//*[@id="materialViewModal"]/div/div/div[1]/button/img'))).click()
        print('닫기 버튼 클릭')
    except NoSuchElementException:
        # tbody나 tr 요소가 존재하지 않는 경우에 대한 예외 처리
        print("해당 항목이 없습니다.")
        wait.until(EC.presence_of_element_located(
            (By.XPATH, '//*[@id="materialViewModal"]/div/div/div[1]/button/img'))).click()
        pass


#####################################################################
#광고 제거 함수
def delete_abs(driver,wait):
    # 구글 광고로 클릭이 안되는 이슈 해결
    # try:
    #     driver.find_element(By.XPATH, '/html/body/div[5]/div/div/div[2]').click()
    #     print('구글광고 닫기 완료')
    # except NoSuchElementException:
    #     pass

    # 광고 모달 닫기
    try:
        time.sleep(3)
        # ad_modal = driver.find_element(By.XPATH, '//*[@id="popup_goods"]/a')
        ad_modal = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="popup_goods"]/a')))
        print('레시피광고 찾기 완료')
        time.sleep(5)
        ad_modal.click()
        print('레시피모달 닫기 완료')
    except NoSuchElementException:
        pass


# 스크롤 값을 받아 특정 위치로 스크롤을 내리는 함수
def scroll_to_position(driver, scroll_value):
    script = "window.scrollTo(0, {});".format(scroll_value)
    driver.execute_script(script)
