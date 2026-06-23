调用开放API_获取app_access_token

# 获取app_access_token
### 1. 基本信息
|**名称**|**说明**|
|-|-|
|**描述**|1、获取应用的访问凭证<br/>2、使用app_access_token可以调用不需要用户身份信息的api|
|**认证方式**|待补充|
|**审批权限**|待补充|
|**前置依赖**|待补充|
|**版本**|待补充|

使用Comate插件快速生成代码（支持python、go、java）：[Comate × 如流机器人插件：快速上线全新智能机器人](https://ku.baidu-int.com/knowledge/HFVrC7hq1Q/2tsPs8CtSd/Bu7DDg4dpB/afxtkGIvkFTKWp#anchor-71ab3b41-308b-11f0-bb5a-cd90eadde8de?t=mention&mt=doc&dt=doc)

### 2. 请求信息
* **请求路径**：/api/v1/auth/app_access_token
* **请求方式**：POST

### 3. 请求参数
#### | Body参数
|**参数名**|**类型**|**必填**|**描述**|**备注**|
|-|-|-|-|-|
|app_key|String|是|标识应用身份的唯一id。应用开发者联系企业管理员获取|[机器人app_key和app_secret获取方式](https://ku.baidu-int.com/knowledge/HFVrC7hq1Q/pKzJfZczuc/L58YT8DcRD/K767zeF1zD4W2m?t=mention&mt=doc&dt=doc)|
|app_secret|String|是|strlower(**md5hex**(app_secret))，app secret是应用身份的私钥，应用方必须保护好私钥安全性，为了提高安全性，**请求这个接口时需要进行md5签名转换**||

### 4. 请求示例
> ⚠️ 以下内容根据已有信息自动生成，请确认
```bash
curl -X POST \
  -H 'Authorization: Bearer {your_token}' \
  -H 'Content-Type: application/json' \
  'https://{host}/api/v1/auth/app_access_token' \
  -d '{
  "app_key": "{app_key}",
  "app_secret": "{app_secret}"
}'
```
接口示例：

开放平台各环境地址：

[工作卡各环境 API 访问地址](https://ku.baidu-int.com/knowledge/HFVrC7hq1Q/2tsPs8CtSd/Bu7DDg4dpB/pqmzP8JmCbEXdB?t=mention&mt=doc&dt=doc)| [快速生成代码DEMO](https://ku.baidu-int.com/knowledge/HFVrC7hq1Q/2tsPs8CtSd/Bu7DDg4dpB/LTv_LxwFwXIbDB?block_id=docyg-19446cf0-094a-11f0-b7a6-91f6ddd8ef45)

```json
POST http://开放平台地址/api/v1/auth/app_access_token
{   
 "app_key":"", 
 "app_secret":"strlower(md5hex(app_secret))"
}
```
### 5. 响应示例
```json
{
    "code": "ok",
    "data": {
        "app_access_token": "xxxxxxxxxxxxxxxx",
        "expire": 7200
    }
}
```
### 6. 响应信息
返回参数：[​](http://localhost:3000/docs/server/get-app-access-token-api#%E8%BF%94%E5%9B%9E%E5%8F%82%E6%95%B0)

|**参数名**|**类型**|**必填**|**描述**|
|-|-|-|-|
|app_access_token|String|是|正常返回的app access token|
|expire|int|是|token有效时间（单位为秒）|

### 请务必注意，生成后的 app_access_token 格式为：at_xxxxxx，在使用时，请添加「Bearer-」的前缀！！！
### 请务必注意，生成后的 app_access_token 格式为：at_xxxxxx，在使用时，请添加「Bearer-」的前缀！！！
### 请务必注意，生成后的 app_access_token 格式为：at_xxxxxx，在使用时，请添加「Bearer-」的前缀！！！
### 7. 错误响应
|**错误码**|**说明**|
|-|-|
|auth.createTokenFail|创建token失败|
|plat.clientError|客户端错误，错误原因参考返回的msg字段|
|auth.appNotFound|应用没找到|
|ok|成功|
|plat.serverError|服务器异常，错误原因参考返回的msg字段|
|auth.invalidAppSecret|非法密钥|