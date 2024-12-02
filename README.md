<div align="center">
  <img src=Others/betterfly-logo.jpg >
</div>

# Betterfly-Server-Python
> *这是一个尝试实现即时通讯软件的项目*
> 
> *本项目基于[QuickIM](https://github.com/Voltline/QuickIM)项目的基本思路，使用Python语言重新开发*

![License](https://img.shields.io/github/license/Voltline/Betterfly-Server-Python)
![Issues](https://img.shields.io/github/issues/Voltline/Betterfly-Server-Python)
![Stars](https://img.shields.io/github/stars/Voltline/Betterfly-Server-Python)

## 成员/Collaborators
* [Voltline](https://github.com/Voltline)
* [D_S_O_](https://github.com/DissipativeStructureObject)

## 项目概况
* 项目开始于2024年10月8日
* 项目基于MIT协议开源
* 本项目仅为Betterfly的服务器部分，客户端部分代码不开源

## Project Brief Introduction
* The project starts on October 8, 2024
* The project based on MIT protocol
* This project is only the server part of Betterfly, and the client-side code will not open source

## 架构/Architecture
<div align="center">
  <img src=Others/betterfly-architecture.svg>
</div>

## 项目信息/About Betterfly-Server-Python
### 语言/Lang
* 语言/Lang：Python
### 第三方库/Third-Party Library
* cos-python-sdk-v5
* pymysql
* httpx[http2]
* pycryptodome

### 开源协议/Open-Source Protocol
* MIT

## Q&A
### 通信协议/Communication Protocol
* 为什么不使用已有的协议？
> 最初构建QuickIM的愿景是在已经学到的计算机网络、操作系统课程的知识体系下完成一个能够完成客户端之间通信的通信软件，因此没有考虑已有的协议

* Why not try to use existed protocol?
> The initial vision for building QuickIM was to create communication software capable of enabling client-to-client communication based on the knowledge framework learned in computer networking and operating systems courses. Therefore, existing protocols were not taken into consideration.

### 技术路线/Technology Roadmap

* 为什么使用Python，而非Java/Golang等更加适合高并发场景的语言？
> 最初的QuickIM基于C++构建，在24年10月开始将其改造为客户端服务的后端后，C++以及一些第三方库带来的问题已经难以解决，在此基础上，为了更快地完成服务器建设，我们决定使用更加简单的Python来解决问题

* Why use Python instead of Java/Golang, which are more suitable for high-concurrency scenarios?
> The initial version of QuickIM was built using C++. However, after starting its transformation into a client-server backend in October 2024, the issues arising from C++ and some third-party libraries became increasingly difficult to resolve. To expedite server development, we decided to switch to the simpler Python to address these challenges.
