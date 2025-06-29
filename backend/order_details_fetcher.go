package main

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// 后端API响应结构体
type BackendStatsResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
	Data    struct {
		IncompleteOrderIDs []string `json:"incomplete_order_ids"`
	} `json:"data"`
}

// 订单详情结构体 - 只定义需要的字段
type OrderDetail struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
	Data    struct {
		OrderDetail struct {
			OrderInfo struct {
				OrderID string `json:"orderId"`
				Status  struct {
					Name string `json:"name"`
				} `json:"status"`
				PaidAt string `json:"paidAt"`
			} `json:"orderInfo"`
			Products []struct {
				ProductName string  `json:"productName"`
				Price       float64 `json:"price"`
				Amount      int     `json:"amount"`
			} `json:"products"`
		} `json:"order_detail"`
	} `json:"data"`
}

// 请求参数结构体
type RequestParams struct {
	XRequestSign      string `json:"x_request_sign"`
	XRequestTimestamp string `json:"x_request_timestamp"`
	Authorization     string `json:"authorization"`
	OrderID           string `json:"order_id"`
}

// 数据库配置
const (
	DB_PATH         = "orders.db"
	API_URL         = "https://api.qiandao.cn/order-web/user/v3/load-order-details"
	BACKEND_API_URL = "http://localhost:8000/api/db-stats"
	MAX_WORKERS     = 200
)

func main() {
	fmt.Println("=== 订单详情获取器 ===")
	
	// 获取用户输入
	params := getUserInput()
	
	// 连接数据库
	db, err := sql.Open("sqlite3", DB_PATH)
	if err != nil {
		log.Fatal("连接数据库失败:", err)
	}
	defer db.Close()
	
	// 1. 从后端API获取incomplete_order_ids
	fmt.Println("正在获取后端API中的incomplete_order_ids...")
	incompleteOrderIDs, err := getIncompleteOrderIDsFromAPI()
	if err != nil {
		log.Fatal("获取incomplete_order_ids失败:", err)
	}
	fmt.Printf("从后端API获取到 %d 个incomplete订单ID\n", len(incompleteOrderIDs))
	
	// 2. 从数据库获取orders_need_details中Complete=FALSE的订单ID
	fmt.Println("正在获取orders_need_details中的未完成订单...")
	needDetailsOrderIDs, err := getOrdersNeedDetails(db)
	if err != nil {
		log.Fatal("获取订单ID列表失败:", err)
	}
	fmt.Printf("从orders_need_details获取到 %d 个未完成订单ID\n", len(needDetailsOrderIDs))
	
	// 3. 合并两个列表并去重
	allOrderIDs := mergeAndDeduplicateOrderIDs(incompleteOrderIDs, needDetailsOrderIDs)
	fmt.Printf("合并去重后共有 %d 个订单需要处理\n", len(allOrderIDs))
	
	if len(allOrderIDs) == 0 {
		fmt.Println("没有需要获取详情的订单")
		return
	}
	
	// 预先删除所有要处理订单的旧记录
	fmt.Println("正在删除旧记录...")
	err = deleteOldRecords(db, allOrderIDs)
	if err != nil {
		log.Fatal("删除旧记录失败:", err)
	}
	fmt.Printf("已删除 %d 个订单的旧记录\n", len(allOrderIDs))
	
	// 并发处理订单
	processOrdersConcurrently(db, allOrderIDs, params)
	
	fmt.Println("所有订单处理完成！")
}

// 获取用户输入
func getUserInput() RequestParams {
	reader := bufio.NewReader(os.Stdin)
	
	fmt.Print("请输入 authorization: ")
	authorization, _ := reader.ReadString('\n')
	authorization = strings.TrimSpace(authorization)
	
	fmt.Print("请输入 x_request_sign: ")
	xRequestSign, _ := reader.ReadString('\n')
	xRequestSign = strings.TrimSpace(xRequestSign)
	
	fmt.Print("请输入 x_request_timestamp: ")
	xRequestTimestamp, _ := reader.ReadString('\n')
	xRequestTimestamp = strings.TrimSpace(xRequestTimestamp)
	
	return RequestParams{
		XRequestSign:      xRequestSign,
		XRequestTimestamp: xRequestTimestamp,
		Authorization:     authorization,
	}
}

// 从后端API获取incomplete_order_ids
func getIncompleteOrderIDsFromAPI() ([]string, error) {
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Get(BACKEND_API_URL)
	if err != nil {
		return nil, fmt.Errorf("调用后端API失败: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("后端API返回错误状态码: %d", resp.StatusCode)
	}
	
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取API响应失败: %v", err)
	}
	
	var response BackendStatsResponse
	err = json.Unmarshal(body, &response)
	if err != nil {
		return nil, fmt.Errorf("解析API响应失败: %v", err)
	}
	
	if !response.Success {
		return nil, fmt.Errorf("后端API返回错误: %s", response.Message)
	}
	
	return response.Data.IncompleteOrderIDs, nil
}

// 从数据库获取需要详细显示的订单ID列表（只获取Complete=FALSE的）
func getOrdersNeedDetails(db *sql.DB) ([]string, error) {
	query := "SELECT order_id FROM orders_need_details WHERE Complete = FALSE ORDER BY id DESC"
	rows, err := db.Query(query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	var orderIDs []string
	for rows.Next() {
		var orderID string
		if err := rows.Scan(&orderID); err != nil {
			return nil, err
		}
		orderIDs = append(orderIDs, orderID)
	}
	
	return orderIDs, nil
}

// 合并两个订单ID列表并去重
func mergeAndDeduplicateOrderIDs(list1, list2 []string) []string {
	orderIDSet := make(map[string]bool)
	var result []string
	
	// 添加第一个列表
	for _, orderID := range list1 {
		if !orderIDSet[orderID] {
			orderIDSet[orderID] = true
			result = append(result, orderID)
		}
	}
	
	// 添加第二个列表
	for _, orderID := range list2 {
		if !orderIDSet[orderID] {
			orderIDSet[orderID] = true
			result = append(result, orderID)
		}
	}
	
	return result
}

// 批量删除旧记录
func deleteOldRecords(db *sql.DB, orderIDs []string) error {
	if len(orderIDs) == 0 {
		return nil
	}
	
	// 开始事务
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("开始事务失败: %v", err)
	}
	defer tx.Rollback()
	
	// 构建IN语句的占位符
	placeholders := make([]string, len(orderIDs))
	args := make([]interface{}, len(orderIDs))
	for i, orderID := range orderIDs {
		placeholders[i] = "?"
		args[i] = orderID
	}
	
	// 批量删除order_products中的记录
	query := fmt.Sprintf("DELETE FROM order_products WHERE 订单编号 IN (%s)", 
		strings.Join(placeholders, ","))
	
	result, err := tx.Exec(query, args...)
	if err != nil {
		return fmt.Errorf("删除order_products记录失败: %v", err)
	}
	
	affected, _ := result.RowsAffected()
	fmt.Printf("从order_products中删除了 %d 条记录\n", affected)
	
	// 提交事务
	err = tx.Commit()
	if err != nil {
		return fmt.Errorf("提交删除事务失败: %v", err)
	}
	
	return nil
}

// 根据订单状态更新Complete标志位（仅更新已存在的记录）
func updateOrderCompleteStatus(db *sql.DB, orderID string, status string) error {
	// 检查订单是否在orders_need_details表中存在
	var count int
	err := db.QueryRow("SELECT COUNT(*) FROM orders_need_details WHERE order_id = ?", orderID).Scan(&count)
	if err != nil {
		return fmt.Errorf("检查订单是否存在失败: %v", err)
	}
	
	// 只有当订单在orders_need_details表中存在时才更新
	if count > 0 {
		// 只有状态为"交易成功"或"交易关闭"才设为TRUE
		if status == "交易成功" || status == "交易关闭" {
			_, err := db.Exec("UPDATE orders_need_details SET Complete = TRUE WHERE order_id = ?", orderID)
			if err != nil {
				return fmt.Errorf("更新订单完成状态失败: %v", err)
			}
			fmt.Printf("订单 %s 状态为 '%s'，设置 Complete = TRUE\n", orderID, status)
		} else {
			_, err := db.Exec("UPDATE orders_need_details SET Complete = FALSE WHERE order_id = ?", orderID)
			if err != nil {
				return fmt.Errorf("更新订单完成状态失败: %v", err)
			}
			fmt.Printf("订单 %s 状态为 '%s'，设置 Complete = FALSE\n", orderID, status)
		}
	} else {
		// 如果订单不在orders_need_details表中，只输出信息但不插入
		fmt.Printf("订单 %s 状态为 '%s'，不在orders_need_details表中，跳过更新\n", orderID, status)
	}
	return nil
}

// 并发处理订单
func processOrdersConcurrently(db *sql.DB, orderIDs []string, params RequestParams) {
	// 创建工作通道
	orderChan := make(chan string, len(orderIDs))
	
	// 填充订单ID到通道
	for _, orderID := range orderIDs {
		orderChan <- orderID
	}
	close(orderChan)
	
	// 创建等待组
	var wg sync.WaitGroup
	
	// 统计变量
	var successCount, failCount int64
	var mu sync.Mutex
	
	// 启动工作协程
	workerCount := MAX_WORKERS
	if len(orderIDs) < MAX_WORKERS {
		workerCount = len(orderIDs)
	}
	
	for i := 0; i < workerCount; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			
			for orderID := range orderChan {
				success := processOrder(db, orderID, params)
				
				mu.Lock()
				if success {
					successCount++
				} else {
					failCount++
				}
				
				if (successCount+failCount)%10 == 0 {
					fmt.Printf("进度: 成功 %d, 失败 %d, 总计 %d/%d\n", 
						successCount, failCount, successCount+failCount, len(orderIDs))
				}
				mu.Unlock()
			}
		}(i)
	}
	
	// 等待所有协程完成
	wg.Wait()
	
	fmt.Printf("处理完成! 成功: %d, 失败: %d, 总计: %d\n", successCount, failCount, successCount+failCount)
}

// 处理单个订单
func processOrder(db *sql.DB, orderID string, params RequestParams) bool {
	// 构建请求参数
	requestParams := RequestParams{
		XRequestSign:      params.XRequestSign,
		XRequestTimestamp: params.XRequestTimestamp,
		Authorization:     params.Authorization,
		OrderID:           orderID,
	}
	
	// 发送HTTP请求
	orderDetail, err := fetchOrderDetail(requestParams)
	if err != nil {
		fmt.Printf("订单 %s 请求失败: %v\n", orderID, err)
		return false
	}
	
	// 保存到数据库
	err = saveOrderToDatabase(db, orderDetail)
	if err != nil {
		fmt.Printf("订单 %s 保存失败: %v\n", orderID, err)
		return false
	}
	
	// 根据订单状态更新Complete标志位
	status := orderDetail.Data.OrderDetail.OrderInfo.Status.Name
	err = updateOrderCompleteStatus(db, orderID, status)
	if err != nil {
		fmt.Printf("订单 %s 更新完成状态失败: %v\n", orderID, err)
		return false
	}
	
	return true
}

// 发送HTTP请求获取订单详情
func fetchOrderDetail(params RequestParams) (*OrderDetail, error) {
	// 构建请求体 - 直接调用外部API
	requestBody := map[string]string{
		"orderId": params.OrderID,
	}
	
	jsonBody, err := json.Marshal(requestBody)
	if err != nil {
		return nil, fmt.Errorf("构建请求体失败: %v", err)
	}
	
	// 创建HTTP请求
	req, err := http.NewRequest("POST", API_URL, bytes.NewBuffer(jsonBody))
	if err != nil {
		return nil, fmt.Errorf("创建请求失败: %v", err)
	}
	
	// 设置完整的请求头（与Python后端完全一致）
	req.Header.Set("Accept-Encoding", "gzip")
	req.Header.Set("X-Request-Version", "5.91.1")
	req.Header.Set("X-Request-Sign-Type", "RSA2")
	req.Header.Set("X-Echo-Teen-Mode", "false")
	req.Header.Set("X-Request-Utm_source", "xiaomi")
	req.Header.Set("X-Request-Package-Sign-Version", "0.0.3")
	req.Header.Set("X-Request-Id", "")
	req.Header.Set("X-Client-Package-Id", "1006")
	req.Header.Set("X-Request-Package-Id", "1006")
	req.Header.Set("X-Device-Id", "6ec1e3cac888f55d")
	req.Header.Set("User-Agent", "Kuril+/5.91.1 (Android 15)")
	req.Header.Set("X-Echo-Install-Id", "ODY5NjE4MjM0NDA2NTAyOTQ5")
	req.Header.Set("Cache-Control", "max-age=3600")
	req.Header.Set("X-Echo-City-Code", "")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Downloadchannel", "xiaomi")
	req.Header.Set("X-Request-Sign-Version", "v1")
	req.Header.Set("Referer", "https://qiandao.cn")
	req.Header.Set("X-Request-Channel", "xiaomi")
	req.Header.Set("X-Echo-Region", "CN")
	req.Header.Set("Accept-Language", "zh-CN")
	req.Header.Set("Host", "api.qiandao.cn")
	req.Header.Set("X-Request-Device", "android")
	
	// 设置动态认证信息
	req.Header.Set("X-Request-Timestamp", params.XRequestTimestamp)
	req.Header.Set("X-Request-Sign", params.XRequestSign)
	req.Header.Set("Authorization", params.Authorization)
	
	// 发送请求
	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("发送请求失败: %v", err)
	}
	defer resp.Body.Close()
	
	// 读取响应并处理gzip解压缩
	var reader io.Reader = resp.Body
	if resp.Header.Get("Content-Encoding") == "gzip" {
		gzipReader, err := gzip.NewReader(resp.Body)
		if err != nil {
			return nil, fmt.Errorf("创建gzip读取器失败: %v", err)
		}
		defer gzipReader.Close()
		reader = gzipReader
	}
	
	body, err := io.ReadAll(reader)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %v", err)
	}
	
	// 解析原始API响应
	var apiResponse struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
		Data    struct {
			Details  map[string]interface{} `json:"details"`
			Products []struct {
				ProductName string  `json:"productName"`
				Price       float64 `json:"price"`
				Amount      int     `json:"amount"`
			} `json:"products"`
		} `json:"data"`
	}
	
	err = json.Unmarshal(body, &apiResponse)
	if err != nil {
		return nil, fmt.Errorf("解析响应失败: %v", err)
	}
	
	// 检查API响应状态
	if apiResponse.Code != 0 {
		return nil, fmt.Errorf("API返回错误: %s", apiResponse.Message)
	}
	
	// 转换为我们的结构体格式
	orderDetail := &OrderDetail{
		Success: true,
		Message: "获取订单详情成功",
		Data: struct {
			OrderDetail struct {
				OrderInfo struct {
					OrderID string `json:"orderId"`
					Status  struct {
						Name string `json:"name"`
					} `json:"status"`
					PaidAt string `json:"paidAt"`
				} `json:"orderInfo"`
				Products []struct {
					ProductName string  `json:"productName"`
					Price       float64 `json:"price"`
					Amount      int     `json:"amount"`
				} `json:"products"`
			} `json:"order_detail"`
		}{},
	}
	
	// 提取订单基本信息
	if orderId, ok := apiResponse.Data.Details["orderId"].(string); ok {
		orderDetail.Data.OrderDetail.OrderInfo.OrderID = orderId
	}
	if paidAt, ok := apiResponse.Data.Details["paidAt"].(string); ok {
		orderDetail.Data.OrderDetail.OrderInfo.PaidAt = paidAt
	}
	if status, ok := apiResponse.Data.Details["status"].(map[string]interface{}); ok {
		if name, ok := status["name"].(string); ok {
			orderDetail.Data.OrderDetail.OrderInfo.Status.Name = name
		}
	}
	
	// 复制商品信息
	orderDetail.Data.OrderDetail.Products = apiResponse.Data.Products
	
	return orderDetail, nil
}

// 将时间戳转换为日期格式
func timestampToDate(timestampStr string) string {
	if timestampStr == "" {
		return ""
	}
	
	timestamp, err := strconv.ParseInt(timestampStr, 10, 64)
	if err != nil {
		return timestampStr
	}
	
	return time.Unix(timestamp, 0).Format("2006-01-02 15:04:05")
}

// 保存订单到数据库
func saveOrderToDatabase(db *sql.DB, orderDetail *OrderDetail) error {
	orderInfo := orderDetail.Data.OrderDetail.OrderInfo
	products := orderDetail.Data.OrderDetail.Products
	
	orderID := orderInfo.OrderID
	if orderID == "" {
		return fmt.Errorf("订单ID为空")
	}
	
	paidAt := timestampToDate(orderInfo.PaidAt)
	status := orderInfo.Status.Name
	
	// 开始事务
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("开始事务失败: %v", err)
	}
	defer tx.Rollback()
	
	// 检查是否有商品，如果没有商品则插入一条空记录
	if len(products) == 0 {
		isComplete := status == "交易成功"
		_, err = tx.Exec(`
			INSERT INTO order_products 
			(订单编号, 交易时间, 状态, 商品名称, 数量, 单价, 金额, Complete)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?)
		`, orderID, paidAt, status, "", 0, 0, 0, isComplete)
		
		if err != nil {
			return fmt.Errorf("插入空记录失败: %v", err)
		}
	} else {
		// 插入每个商品记录
		for _, product := range products {
			productName := product.ProductName
			amount := product.Amount
			price := int(product.Price) // 向下取整
			totalAmount := price * amount
			
			isComplete := status == "交易成功"
			
			_, err = tx.Exec(`
				INSERT INTO order_products 
				(订单编号, 交易时间, 状态, 商品名称, 数量, 单价, 金额, Complete)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?)
			`, orderID, paidAt, status, productName, amount, price, totalAmount, isComplete)
			
			if err != nil {
				return fmt.Errorf("插入商品记录失败: %v", err)
			}
		}
	}
	
	// 提交事务
	err = tx.Commit()
	if err != nil {
		return fmt.Errorf("提交事务失败: %v", err)
	}
	
	return nil
} 


/*
进度: 成功 180, 失败 0, 总计 180/371
进度: 成功 190, 失败 0, 总计 190/371
进度: 成功 200, 失败 0, 总计 200/371
进度: 成功 210, 失败 0, 总计 210/371
进度: 成功 220, 失败 0, 总计 220/371
进度: 成功 230, 失败 0, 总计 230/371
进度: 成功 240, 失败 0, 总计 240/371
进度: 成功 250, 失败 0, 总计 250/371
进度: 成功 260, 失败 0, 总计 260/371
进度: 成功 270, 失败 0, 总计 270/371
进度: 成功 280, 失败 0, 总计 280/371
进度: 成功 290, 失败 0, 总计 290/371
进度: 成功 300, 失败 0, 总计 300/371
进度: 成功 310, 失败 0, 总计 310/371
进度: 成功 320, 失败 0, 总计 320/371
进度: 成功 330, 失败 0, 总计 330/371
进度: 成功 340, 失败 0, 总计 340/371
进度: 成功 350, 失败 0, 总计 350/371
进度: 成功 360, 失败 0, 总计 360/371
进度: 成功 370, 失败 0, 总计 370/371
处理完成! 成功: 371, 失败: 0, 总计: 371
所有订单处理完成！
当前记录数：24039
*/

/*
正在获取后端API中的incomplete_order_ids...
从后端API获取到 142 个incomplete订单ID
正在获取orders_need_details中的未完成订单...
从orders_need_details获取到 5 个未完成订单ID
合并去重后共有 144 个订单需要处理
正在删除旧记录...
从order_products中删除了 226 条记录
已删除 144 个订单的旧记录
订单 879628403044795181 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 880132373433596046 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 880132531273625654 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 880131968632916687 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 880132923189397703 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 880135646198676379 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878909310629064913 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 880128823643101578 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878915232315241301 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878913430576448097 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
进度: 成功 10, 失败 0, 总计 10/144
订单 878710564238701944 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878898427181932661 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878912640302470671 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878912478167489293 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878934786227606489 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878906846391598718 状态为 '交易关闭'，不在orders_need_details表中，跳过更新
订单 878934150572454663 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878706345507055863 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878935667769659364 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878909631677910337 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
进度: 成功 20, 失败 0, 总计 20/144
订单 878896218495014837 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878704263521634917 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878904224314035669 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878912547960658509 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878908433382010032 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878906480245648432 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 879628114208227563 状态为 '待买家收货'，设置 Complete = FALSE
订单 878264426658314585 状态为 '卖家同意退货退款，待买家退货'，不在orders_need_details表中，跳
过更新
订单 880139124048407789 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 879654258747914602 状态为 '待买家收货'，设置 Complete = FALSE
进度: 成功 30, 失败 0, 总计 30/144
订单 880133874524641847 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 880137601482523184 状态为 '待卖家发货'，设置 Complete = FALSE
订单 880132306861616144 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878895952207020662 状态为 '交易关闭'，不在orders_need_details表中，跳过更新
订单 880128294288408661 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878908695375033796 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878895267159743752 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 879628503976566179 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 880135740687967919 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 880138004135733778 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
进度: 成功 40, 失败 0, 总计 40/144
订单 879627905902330000 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878936037136811228 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 880135147982486117 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878911353959790773 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878910329610091511 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 880129540902661861 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878911108072885528 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878904148078412776 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 880137729257796139 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878704121787759583 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
进度: 成功 50, 失败 0, 总计 50/144
订单 878909989233885820 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878912317106198371 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878909046488628122 状态为 '交易关闭'，不在orders_need_details表中，跳过更新
订单 878910564759545927 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878935417587789345 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878910211498474423 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878265564824629511 状态为 '交易关闭'，不在orders_need_details表中，跳过更新
订单 880133388119615696 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 880135045976960707 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 880133640448938684 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
进度: 成功 60, 失败 0, 总计 60/144
订单 880131895618464791 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878909899039631313 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 880135573184224705 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878905341005558881 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878914986428394013 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 880138203851696762 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878913919128995308 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 880137858106827893 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878709653705596683 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 877934630078270463 状态为 '交易关闭'，不在orders_need_details表中，跳过更新
进度: 成功 70, 失败 0, 总计 70/144
订单 878898594685672930 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878895016977914833 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878703540893423378 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 880133773592939806 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878905249737486042 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 877934778254671116 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 880132870576076299 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878914309971050415 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878908135955560998 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 880131322240337078 状态为 '待卖家发货'，设置 Complete = FALSE
进度: 成功 80, 失败 0, 总计 80/144
订单 878934683148382724 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878912142086288836 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878910452016660713 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878203456376291472 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878935893255445885 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 880135255356612983 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878702699079799629 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 880135333739798981 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878913211533102261 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878897443634463067 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
进度: 成功 90, 失败 0, 总计 90/144
订单 878896288288220330 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878267639293818536 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878913677537080935 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 880133950760321415 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 877486381634447057 状态为 '卖家同意退货退款，待买家退货'，不在orders_need_details表中，跳
过更新
订单 874564486278991594 状态为 '已退货，待卖家收货'，不在orders_need_details表中，跳过更新
订单 878896410694800833 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878702659351371241 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 880134406026836170 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878203001109787014 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
进度: 成功 100, 失败 0, 总计 100/144
订单 878908053277382736 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878703388422091076 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878710971186821592 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878705192308372158 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878907511037756820 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878909201107396021 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878942769498046515 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 880132757833164767 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878908629876770343 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878903979500948024 状态为 '交易成功'，不在orders_need_details表中，跳过更新
进度: 成功 110, 失败 0, 总计 110/144
订单 878907768735820016 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 874079623125970645 状态为 '交易关闭'，不在orders_need_details表中，跳过更新
订单 880130013349046965 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878896491225469815 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878897135470555143 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878897035612531367 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878903668115803644 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878202764886570754 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878703160788800350 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878895115762170411 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
进度: 成功 120, 失败 0, 总计 120/144
订单 874527272534839053 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878905423683670873 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878703208033445410 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878905884318909836 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878703910260586245 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878908545051166918 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878899306576521895 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878909451289269729 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878915296739759159 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878702600295604964 状态为 '交易成功'，不在orders_need_details表中，跳过更新
进度: 成功 130, 失败 0, 总计 130/144
订单 878906246169912707 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878912253755447380 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878704360158425731 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878898950094201943 状态为 '待卖家发货'，设置 Complete = FALSE
订单 878912717611887807 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878907422990925928 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878896949713178969 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878942658902649309 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878894767869789717 状态为 '待买家收货'，不在orders_need_details表中，跳过更新
订单 878703262794268285 状态为 '交易成功'，不在orders_need_details表中，跳过更新
进度: 成功 140, 失败 0, 总计 140/144
订单 878706413152821546 状态为 '待卖家发货'，不在orders_need_details表中，跳过更新
订单 878911967066343033 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878897644424154832 状态为 '交易成功'，不在orders_need_details表中，跳过更新
订单 878266583805641514 状态为 '交易关闭'，不在orders_need_details表中，跳过更新
处理完成! 成功: 144, 失败: 0, 总计: 144
所有订单处理完成！
*/