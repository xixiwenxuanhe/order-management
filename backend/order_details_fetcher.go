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
	DB_PATH    = "orders.db"
	API_URL    = "https://api.qiandao.cn/order-web/user/v3/load-order-details"
	MAX_WORKERS = 200
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
	
	// 获取需要详细显示的订单ID列表
	orderIDs, err := getOrdersNeedDetails(db)
	if err != nil {
		log.Fatal("获取订单ID列表失败:", err)
	}
	
	if len(orderIDs) == 0 {
		fmt.Println("没有需要获取详情的订单")
		return
	}
	
	fmt.Printf("找到 %d 个需要获取详情的订单\n", len(orderIDs))
	
	// 并发处理订单
	processOrdersConcurrently(db, orderIDs, params)
	
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

// 标记订单为已完成
func markOrderAsComplete(db *sql.DB, orderID string) error {
	_, err := db.Exec("UPDATE orders_need_details SET Complete = TRUE WHERE order_id = ?", orderID)
	if err != nil {
		return fmt.Errorf("更新订单完成状态失败: %v", err)
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
	
	// 标记该订单为已完成
	err = markOrderAsComplete(db, orderID)
	if err != nil {
		fmt.Printf("订单 %s 标记完成失败: %v\n", orderID, err)
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
	
	// 删除该订单的旧记录
	_, err = tx.Exec("DELETE FROM order_products WHERE 订单编号 = ?", orderID)
	if err != nil {
		return fmt.Errorf("删除旧记录失败: %v", err)
	}
	
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