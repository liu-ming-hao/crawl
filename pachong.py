from pyclbr import Class
import pymysql
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyquery import PyQuery as pq
import time
import random
import math
from datetime import datetime


from flask import Flask, request, jsonify

app = Flask(__name__)




# 数据库中要插入的表
MYSQL_TABLE = 'goods'
MYSQL_TABLE_AMAZON = 'goods_amazon'

# MySQL 数据库连接配置,根据自己的本地数据库修改
db_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'admin',
    'database': 'datavisible',
    'charset': 'utf8mb4',
}



# ================== 淘宝 爬虫 ==================
# ==============================================
# 打开页面后会强制停止10秒，请在此时手动扫码登陆
def search_goods_taobao(start_page, total_pages, driver, wait, cursor, conn, web_url, web_keyword, crawl_num,goods_list):
    print('正在搜索: ')
    try:
        #https://www.taobao.com
        driver.get(web_url)
        # 强制停止10秒，请在此时手动扫码登陆
        time.sleep(10)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                           {"source": """Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"""})
        
        # ================== 点击“搜索”按钮 ==================
        # 找到搜索输入框
        input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#q")))
        # 找到“搜索”按钮
        submit = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'#J_TSearchForm > div.search-button > button')))
        input.send_keys(web_keyword)
        submit.click()
        # 每次操作后，切换到最新窗口
        driver.switch_to.window(driver.window_handles[-1])

        print("开始等待")
        time.sleep(5)
        print("等待结束")

        # ================== 点击“销量”按钮 ==================
        # 找到“销量”按钮
        # 尝试使用JavaScript执行点击，这通常更可靠
        ul_element = wait.until(EC.element_to_be_clickable((By.XPATH,'//*[@id="sortBarWrap_filterListWrapper"]/div/div[1]/div/div/div/ul[@class="next-tabs-nav"]/li[2]')))
        ul_element.click()
        # 搜索后，切换到最新窗口
        driver.switch_to.window(driver.window_handles[-1])

        # 搜索商品后会再强制停止10秒，如有滑块请手动操作
        print('搜索商品后会再强制停止10秒，如有滑块请手动操作')
        time.sleep(10)
        print('搜索商品后会再强制停止10秒，如有滑块请手动操作---------------')


        get_goods_taobao(driver,cursor,conn,crawl_num,goods_list)

        # 判断goods_list的长度是否小于crawl_num
        if len(goods_list) < crawl_num:
            print("商品数量小于crawl_num，继续爬取")

            # 通过goods_list的长度以及crawl_num计算需要爬取的页数
            total_pages = math.ceil(crawl_num / len(goods_list))
            for i in range(start_page + 1, total_pages + 1):
                page_turning(i,wait,driver,cursor,conn,crawl_num,goods_list)
        else:
            print("商品数量达到上限，停止爬取")
            
        # goods_list只保留前crawl_num个商品
        goods_list = goods_list[:crawl_num]
        for i in goods_list:
            save_to_mysql(i,cursor,conn)

        # for i in range(start_page + 1, start_page + total_pages):
        #     page_turning(i,wait,driver,cursor,conn,crawl_num,goods_list)
    except TimeoutException:
        print("search_goods: TimeoutException error")

        #return search_goods(start_page, total_pages, driver, wait, cursor, conn, web_url, web_keyword)
    
# 进行翻页处理
def page_turning(page_number,wait,driver,cursor,conn,crawl_num,goods_list):
    print('正在翻页: ', page_number)
    try:
        # 找到下一页的按钮
        submit = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@class="pgWrap--RTFKoWa6"]/div/div/button[2]')))
        submit.click()
        time.sleep(5)
        driver.switch_to.window(driver.window_handles[-1])
        # 获取页面链接中的页数
        page_number = driver.current_url.split('&')[3]
        print("当前页数: ", page_number)
        get_goods_taobao(driver,cursor,conn,crawl_num,goods_list)
    except TimeoutException:
        print("page_turning: TimeoutException error")
        # page_turning(page_number,wait,driver,cursor,conn,crawl_num,goods_list)

#获取每一页的商品信息；
def get_goods_taobao(driver,cursor,conn,crawl_num,goods_list):
    print('正在获取商品信息: ')
    # 获取当前页面的完整URL
    current_url = driver.current_url
    print(f"当前页面链接: {current_url}")
    # 获取商品前固定等待2-4秒
    random_sleep(2, 4)
    #time.sleep(20)
    print('成成等待时间')
    html = driver.page_source
    print('页面源码获取成功')
    doc = pq(html)
    print('页面源码解析成功')
    # 提取所有商品的共同父元素的类选择器
    #items = doc('div.PageContent--contentWrap--mep7AEm > div.LeftLay--leftWrap--xBQipVc > div.LeftLay--leftContent--AMmPNfB > div.Content--content--sgSCZ12 > div.Content--contentInner--QVTcU0M > a.CardV2--doubleCardWrapper--rq81FGu').items()
    items = doc('a.doubleCardWrapperAdapt--mEcC7olq').items()

    #compare_with_crawl_num = 0
    for item in items:
        #print('正在提取商品信息: ')

        # ================== 从列表页提取商品信息 ==================
        # 定位商品标题
        title = item.find('div.title--qJ7Xg_90  span').text()
        # 定位价格
        price_int = item.find('div.priceInt--yqqZMJ5a').text()
        price_float = item.find('div.priceFloat--XpixvyQ1').text()
        if price_int:
            if price_float:
                price = float(f"{price_int}{price_float}")
            else:
                price = float(f"{price_int}.00")
        else:
            price = 0.0
        # 定位交易量
        deal = item.find('.Price--realSales--FhTZc7U').text()
        # 定位所在地信息
        location = item.find('.Price--procity--_7Vt3mX').text()
        # 定位店名
        shop = item.find('.ShopInfo--TextAndPic--yH0AZfx a').text()
        # 定位包邮的位置
        postText = item.find('.SalesPoint--subIconWrapper--s6vanNY span').text()
        result = 1 if "包邮" in postText else 0

        # 定位商品图片
        pic_src = item.find('img.mainImg--sPh_U37m').attr('src')


        # ================== 从详情页提取商品信息 ==================
        # 获取商品的链接地址
        # 使用PyQuery正确的方式获取href属性
        # item_href = item.attr('href')
        # if item_href:
        #     # 确保链接是完整的URL
        #     if not str(item_href).startswith('http'):
        #         item_href = 'https:' + str(item_href)
            
        #     print(f"点击进入商品详情页: {item_href}")
            
        #     # 保存当前页面的URL以便之后返回
        #     current_page_url = driver.current_url
            
        #     # 打开商品详情页
        #     driver.get(item_href)
            
        #     # 等待详情页加载
        #     random_sleep(2, 3)
            
        #     # 在这里可以添加详情页的爬取逻辑
        #     # ...
            
        #     # 处理完成后返回到商品列表页
        #     # driver.back()
            
        #     # 等待列表页重新加载
        #     # random_sleep(1, 2)
        


        # 构建商品信息字典
        product = {
            'title': title,
            'price': price,
            'deal': deal,
            'location': location,
            'shop': shop,
            'isPostFree': result,
            'pic_src': pic_src
        }
        #print('商品信息提取成功: ', product)
        goods_list.append(product)
        # if compare_with_crawl_num < crawl_num:
        #     goods_list.append(product)
        #     compare_with_crawl_num += 1
        #     save_to_mysql(product,cursor,conn)
        # else:
        #     break





# ================== 1688 爬虫 ==================
# ==============================================
# 打开页面后会强制停止10秒，请在此时手动扫码登陆
def search_goods_1688(start_page, total_pages, driver, wait, cursor, conn, web_url, web_keyword, crawl_num,goods_list):
    print('正在搜索: ')
    try:
        #https://www.taobao.com
        driver.get(web_url)
        # 强制停止10秒，请在此时手动扫码登陆
        time.sleep(20)
        print('设置脚本')
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                           {"source": """Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"""})
        # 找到搜索输入框
        print('寻找输入框')
        input = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ali-search-input")))
        # 找到“搜索”按钮
        print('定位搜索按钮')
        submit = wait.until(EC.element_to_be_clickable((By.CLASS_NAME,'input-button')))
        print('键入搜索内容')
        input.send_keys(web_keyword)
        print('点击')
        submit.click()
        # 搜索商品后会再强制停止10秒，如有滑块请手动操作
        print('搜索商品后会再强制停止10秒，如有滑块请手动操作')
        time.sleep(10)
        print('搜索商品后会再强制停止10秒，如有滑块请手动操作---------------')
        # 搜索后，切换到最新窗口
        driver.switch_to.window(driver.window_handles[-1])
        # 如果不是从第一页开始爬取，就滑动到底部输入页面然后跳转
        if start_page != 1 :
            # 滑动到页面底端
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # 滑动到底部后停留1-3s
            random_sleep(1, 3)

            # 找到输入页面的表单
            pageInput = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="root"]/div/div[3]/div[1]/div[1]/div[2]/div[4]/div/div/span[3]/input')))
            pageInput.send_keys(start_page)
            # 找到页面跳转的确定按钮，并且点击
            admit = wait.until(EC.element_to_be_clickable((By.XPATH,'//*[@id="root"]/div/div[3]/div[1]/div[1]/div[2]/div[4]/div/div/button[3]')))
            admit.click()

        get_goods_1688(driver,cursor,conn,crawl_num,goods_list)

        for i in range(start_page + 1, start_page + total_pages):
            page_turning(i,wait,driver,cursor,conn,crawl_num,goods_list)
    except TimeoutException:
        print("search_goods_1688: error")
        #return search_goods(start_page, total_pages, driver, wait, cursor, conn, web_url, web_keyword)
    
#获取每一页的商品信息；
def get_goods_1688(driver,cursor,conn,crawl_num,goods_list):
    print('正在获取商品信息: ')
    # 获取当前页面的完整URL
    current_url = driver.current_url
    print(f"当前页面链接: {current_url}")
    # 获取商品前固定等待2-4秒
    random_sleep(2, 4)
    #time.sleep(20)
    print('成成等待时间')
    html = driver.page_source
    print('页面源码获取成功')
    doc = pq(html)
    print('页面源码解析成功')
    # 提取所有商品的共同父元素的类选择器
    #items = doc('div.PageContent--contentWrap--mep7AEm > div.LeftLay--leftWrap--xBQipVc > div.LeftLay--leftContent--AMmPNfB > div.Content--content--sgSCZ12 > div.Content--contentInner--QVTcU0M > a.CardV2--doubleCardWrapper--rq81FGu').items()
    items = doc('div.feeds-wrapper > a.search-offer-wrapper').items()
    print('提取所有商品的共同父元素的类选择器')

    compare_with_crawl_num = 0
    for item in items:
        #print('正在提取商品信息: ')
        # 定位商品标题
        title = item.find('div.title-text div').text()
        # 定位价格
        price_int = item.find('div.offer-price-row div.col-desc div.price-item div.text-main').text()
        #print("价格int位",price_int)
        price_float = item.find('div.offer-price-row div.col-desc div.price-item div:not([class])').text()
        #print("价格float位",price_float)
        if price_int:
            if price_float:
                price = float(f"{price_int}{price_float}")
            else:
                price = float(f"{price_int}.00")
        else:
            price = 0.0
        # 定位交易量
        deal = item.find('.Price--realSales--FhTZc7U').text()
        # 定位所在地信息
        location = item.find('.Price--procity--_7Vt3mX').text()
        # 定位店名
        shop = item.find('.ShopInfo--TextAndPic--yH0AZfx a').text()
        # 定位包邮的位置
        postText = item.find('.SalesPoint--subIconWrapper--s6vanNY span').text()
        result = 1 if "包邮" in postText else 0

        # 定位商品图片
        pic_src = item.find('img.main-img').attr('src')

        # 构建商品信息字典
        product = {
            'title': title,
            'price': price,
            'deal': deal,
            'location': location,
            'shop': shop,
            'isPostFree': result,
            'pic_src': pic_src
        }
        #print('商品信息提取成功: ', product)
        if compare_with_crawl_num < crawl_num:
            goods_list.append(product)
            compare_with_crawl_num += 1
            save_to_mysql(product,cursor,conn)
        else:
            break







# ================== 亚马逊 爬虫 ==================
# ==============================================
# 打开页面后会强制停止10秒，请在此时手动扫码登陆
def search_goods_amazon(start_page, total_pages, driver, wait, cursor, conn, web_url, web_keyword, crawl_num,goods_list):
    print('正在搜索: ')
    try:
        #https://www.taobao.com
        driver.get(web_url)
        # 强制停止10秒，请在此时手动扫码登陆
        time.sleep(3)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                           {"source": """Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"""})
        
        # ================== 点击“搜索”按钮 ==================
        # 找到搜索输入框
        input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#twotabsearchtextbox")))
        # 找到“搜索”按钮
        submit = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'#nav-search-submit-button')))
        input.send_keys(web_keyword)
        submit.click()
        # 每次操作后，切换到最新窗口
        driver.switch_to.window(driver.window_handles[-1])

        print("开始等待")
        time.sleep(5)
        print("等待结束")

        # ================== 点击“销量”按钮 ==================
        # 找到“排序”按钮
        sort_element = wait.until(EC.element_to_be_clickable((By.XPATH,'//span[@id="a-autoid-0-announce"]')))
        sort_element.click()
        # 搜索后，切换到最新窗口
        driver.switch_to.window(driver.window_handles[-1])

        print("开始等待")
        time.sleep(3)
        print("等待结束")

        # 找到“销量”按钮
        ul_element = wait.until(EC.element_to_be_clickable((By.XPATH,'//div[@class="a-popover-inner"]/ul/li[6]')))
        ul_element.click()
        driver.switch_to.window(driver.window_handles[-1])

        # 搜索商品后会再强制停止10秒，如有滑块请手动操作
        print('搜索商品后会再强制停止10秒，如有滑块请手动操作')
        time.sleep(5)
        print('搜索商品后会再强制停止10秒，如有滑块请手动操作---------------')


        get_goods_amazon(driver,cursor,conn,crawl_num,goods_list)
        # array转字符串输出goods_list

        # 判断goods_list的长度是否小于crawl_num
        if len(goods_list) < crawl_num:
            print("商品数量小于crawl_num，继续爬取")

            # 通过goods_list的长度以及crawl_num计算需要爬取的页数
            total_pages = math.ceil(crawl_num / len(goods_list))
            for i in range(start_page + 1, total_pages + 1):
                page_turning_amazon(i,wait,driver,cursor,conn,crawl_num,goods_list)
                if len(goods_list) >= crawl_num:
                    break
        else:
            print("商品数量达到上限，停止爬取")
            
        # goods_list只保留前crawl_num个商品
        print("goods_list长度为: ", len(goods_list))
        print("开始截取goods_list")
        if len(goods_list) > crawl_num:
            goods_list = goods_list[:crawl_num]
        print("开始保存goods_list到数据库")
        for i in goods_list:
            save_to_mysql_amazon(i,cursor,conn)

        # for i in range(start_page + 1, start_page + total_pages):
        #     page_turning(i,wait,driver,cursor,conn,crawl_num,goods_list)
    except TimeoutException:
        print("search_goods: TimeoutException error")

        #return search_goods(start_page, total_pages, driver, wait, cursor, conn, web_url, web_keyword)
    
# 进行翻页处理
def page_turning_amazon(page_number,wait,driver,cursor,conn,crawl_num,goods_list):
    print('正在翻页: ', page_number)
    try:
        # 找到下一页的按钮
        submit = wait.until(EC.element_to_be_clickable((By.XPATH, '//li[@class="s-list-item-margin-right-adjustment"][last()]/span/a')))
        submit.click()
        time.sleep(5)
        driver.switch_to.window(driver.window_handles[-1])
        # 获取页面链接中的页数
        page_number = driver.current_url.split('&')[2]
        print("当前页数: ", page_number)
        get_goods_amazon(driver,cursor,conn,crawl_num,goods_list)
    except TimeoutException:
        print("page_turning: TimeoutException error")
        # page_turning(page_number,wait,driver,cursor,conn,crawl_num,goods_list)

#获取每一页的商品信息；
def get_goods_amazon(driver,cursor,conn,crawl_num,goods_list):
    print('正在获取商品信息: ')
    # 获取当前页面的完整URL
    current_url = driver.current_url
    print(f"当前页面链接: {current_url}")
    # 获取商品前固定等待2-4秒
    random_sleep(2, 4)
    #time.sleep(20)
    print('成成等待时间')
    html = driver.page_source
    print('页面源码获取成功')
    doc = pq(html)
    print('页面源码解析成功')
    # 提取所有商品的共同父元素的类选择器
    #items = doc('div.PageContent--contentWrap--mep7AEm > div.LeftLay--leftWrap--xBQipVc > div.LeftLay--leftContent--AMmPNfB > div.Content--content--sgSCZ12 > div.Content--contentInner--QVTcU0M > a.CardV2--doubleCardWrapper--rq81FGu').items()
    items = doc('div.s-main-slot > div.sg-col-4-of-24').items()

    #compare_with_crawl_num = 0
    for item in items:
        #print('正在提取商品信息: ')

        # ================== 从列表页提取商品信息 ==================
        
        # 定位商品标题
        title = item.find('h2.a-size-base-plus  span').text()
        print("商品标题",title)
        
        # 定位价格
        # 价格单位
        price_unit = item.find('span.a-price-symbol').text()
        print("价格单位",price_unit)
        # 如果价格单位为空，则开始下次循环
        if not price_unit:
            continue
        price_int = item.find('span.a-price-whole').text()
        print("价格整数位",price_int)
        price_float = item.find('span.a-price-fraction').text()
        print("价格小数位",price_float)
        if price_int:
            if price_float:
                price = float(f"{price_int}{price_float}")
            else:
                price = float(f"{price_int}.00")
        else:
            price = 0.0
        print("商品价格",price)

        # 定位交易量
        deal = item.find('div[data-cy="reviews-block"] div:nth-of-type(2) span').text()
        deal_numbers = [c for c in deal if c.isdigit() or c == '.']
        deal_month = ''.join(deal_numbers)
        print("月交易量",deal_month)
        if not deal_month:
            continue

        # 根据交易量和价格计算销售额
        sales_month = float(deal_month) * price
        print("月销售额",sales_month)

        # 商品评分
        rating = item.find('span.a-icon-alt').text()
        rating_numbers = [c for c in rating if c.isdigit() or c == '.']
        # 去掉最后一个数字
        rating = ''.join(rating_numbers[:-1])
        print("商品评分",rating)

        # 商品评价数量
        reviews = item.find('div[data-cy="reviews-block"] div:nth-of-type(1) span.a-size-base').text()
        print("商品评价数量",reviews)

        # 定位所在地信息
        location = item.find('.Price--procity--_7Vt3mX').text()
        # 定位店名
        shop = item.find('.ShopInfo--TextAndPic--yH0AZfx a').text()
        # 定位包邮的位置
        postText = item.find('.SalesPoint--subIconWrapper--s6vanNY span').text()
        result = 1 if "包邮" in postText else 0

        # 定位商品图片
        pic_src = item.find('div.s-product-image-container span a div img').attr('src')


        # ================== 从详情页提取商品信息 ==================
        # 获取商品的链接地址
        # 使用PyQuery正确的方式获取href属性
        item_href = item.find('div[data-cy="title-recipe"] a.a-link-normal').attr('href')
        if item_href:
            # 确保链接是完整的URL
            if not str(item_href).startswith('http'):
                item_href = 'https://www.amazon.com' + str(item_href)
            
            print(f"点击进入商品详情页: {item_href}")
            
            # 保存当前页面的URL以便之后返回
            current_page_url = driver.current_url
            
            # 打开商品详情页
            driver.get(item_href)
            
            # 等待详情页加载
            random_sleep(2, 3)

            detail_html = driver.page_source
            detail_doc = pq(detail_html)

            
            # 在这里可以添加详情页的爬取逻辑
            # 品牌
            brand = detail_doc.find('div[id="productDetails_expanderTables_depthLeftSections"] div:nth-of-type(1) div div table tbody tr:nth-of-type(1) td').text()
            print("品牌",brand)
            if not brand:             
                # 处理完成后返回到商品列表页
                driver.back()
                
                # 等待列表页重新加载
                random_sleep(1, 2)

                continue

            # 自营标识: 配送方为 Amazon.com，卖家为 Amazon.com
            delivery_party = detail_doc.find('div[id="a-popover-offerDisplayFeatureFulfillerInfoPopover-0"] div div:nth-of-type(2)').text()
            print("配送方",delivery_party)
            seller = detail_doc.find('div[id="a-popover-offerDisplayFeatureMerchantInfoPopover-0"] div div:nth-of-type(2)').text()
            print("卖家",seller)

            # 配送方为 Amazon.com，卖家为 Amazon.com
            seller_type = ""
            if delivery_party == "Amazon.com" and seller == "Amazon.com":
                seller_type = "自营"
            else:
                seller_type = "非自营"


            # 处理完成后返回到商品列表页
            driver.back()
            
            # 等待列表页重新加载
            random_sleep(1, 2)
        


        # 构建商品信息字典
        product = {
            'title': title,
            'price': price,
            'deal_month': deal_month,
            'sales_month': sales_month,
            'rating': rating,
            'reviews': reviews,
            'delivery_party': delivery_party,
            'seller': seller,
            'pic_src': pic_src,
            'item_href': item_href,
            # 非数据库字段
            'seller_type': seller_type
        }
        #print('商品信息提取成功: ', product)
        goods_list.append(product)

        if len(goods_list) >= crawl_num:
            break
        # if compare_with_crawl_num < crawl_num:
        #     goods_list.append(product)
        #     compare_with_crawl_num += 1
        #     save_to_mysql(product,cursor,conn)
        # else:
        #     break


def save_to_mysql_amazon(result,cursor,conn):
    try:
        # create_time 当前时间
        create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql = "INSERT INTO {} (create_time, title, price, deal_month, sales_month, rating, reviews, delivery_party, seller, pic_src, item_href) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)".format(MYSQL_TABLE_AMAZON)
        #print("sql语句为:  "  + sql)
        cursor.execute(sql, (create_time, result['title'], result['price'], result['deal_month'], result['sales_month'], result['rating'], result['reviews'], result['delivery_party'], result['seller'], result['pic_src'], result['item_href']))
        conn.commit()
        #print('存储到MySQL成功: ', result)
    except Exception as e:
        print('存储到MYsql出错: ', result, e)


# 在 save_to_mysql 函数中保存数据到 MySQL
def save_to_mysql(result,cursor,conn):
    try:
        sql = "INSERT INTO {} (price, deal, title, shop, location, isPostFree, pic_src) VALUES (%s, %s, %s, %s, %s, %s, %s)".format(MYSQL_TABLE)
        #print("sql语句为:  "  + sql)
        cursor.execute(sql, (result['price'], result['deal'], result['title'], result['shop'], result['location'], result['isPostFree'], result['pic_src']))
        conn.commit()
        #print('存储到MySQL成功: ', result)
    except Exception as e:
        print('存储到MYsql出错: ', result, e)
        


# 强制等待的方法，在timeS到timeE的时间之间随机等待
def random_sleep(timeS, timeE):
    # 生成一个S到E之间的随机等待时间
    random_sleep_time = random.uniform(timeS, timeE)
    time.sleep(random_sleep_time)

# 在 main 函数开始时连接数据库
# def main():
#     try:
#         pageStart = int(input("输入您想开始爬取的页面数: "))
#         pageAll = int(input("输入您想爬取的总页面数: "))
#         search_goods(pageStart, pageAll)
#     except Exception as e:
#         print('main函数报错: ', e)
#     finally:
#         cursor.close()
#         conn.close()

#启动爬虫
# if __name__ == '__main__':
#     main()


def run_spider(pageStart, pageAll, web_url, web_keyword, crawl_num):
    # 创建 MySQL 连接对象
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()

    options = webdriver.ChromeOptions()
    # 关闭自动测试状态显示 // 会导致浏览器报：请停用开发者模式
    options.add_experimental_option("excludeSwitches", ['enable-automation'])

    # 把chrome设为selenium驱动的浏览器代理；
    driver = webdriver.Chrome(options=options)
    # 窗口最大化
    driver.maximize_window()

    # wait是Selenium中的一个等待类，用于在特定条件满足之前等待一定的时间(这里是15秒)。
    # 如果一直到等待时间都没满足则会捕获TimeoutException异常
    wait = WebDriverWait(driver, 15)

    # 定义一个列表，用于存储爬取的商品信息
    goods_list = []
    try:
        if web_url == 'https://www.taobao.com':
            search_goods_taobao(pageStart, pageAll, driver, wait, cursor, conn, web_url, web_keyword, crawl_num,goods_list)
        elif web_url == 'https://www.1688.com':
            search_goods_1688(pageStart, pageAll, driver, wait, cursor, conn, web_url, web_keyword, crawl_num,goods_list)
        elif web_url == 'https://www.amazon.com':
            search_goods_amazon(pageStart, pageAll, driver, wait, cursor, conn, web_url, web_keyword, crawl_num,goods_list)
        return {"status": "success", "goods_list": goods_list[:crawl_num]}
    except Exception as e:
        print("主函数出错：" , e)
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        conn.close()
        #driver.quit()


@app.route('/run_spider', methods=['POST'])
def run_spider_api():
    data = request.get_json()
    pageStart = int(data.get('pagestart', 1))
    pageAll = int(data.get('pageall', 1))

    web_url = data.get('web_url', 'https://www.taobao.com')
    web_keyword = data.get('web_keyword', '衣服')
    crawl_num = int(data.get('crawl_num', 1))

    result = run_spider(pageStart, pageAll, web_url, web_keyword, crawl_num)
    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3003)



