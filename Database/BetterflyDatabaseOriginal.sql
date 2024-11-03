/*
 Navicat Premium Dump SQL

 Source Server         : Lighthouse Server
 Source Server Type    : MySQL
 Source Server Version : 80039 (8.0.39-0ubuntu0.22.04.1)
 Source Host           :
 Source Schema         : Betterfly

 Target Server Type    : MySQL
 Target Server Version : 80039 (8.0.39-0ubuntu0.22.04.1)
 File Encoding         : 65001

 Date: 03/11/2024 13:48:35
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for contacts
-- ----------------------------
DROP TABLE IF EXISTS `contacts`;
CREATE TABLE `contacts`  (
  `user_id` int NOT NULL COMMENT '我',
  `contact_id` int NOT NULL COMMENT '别人',
  `notify` int NOT NULL DEFAULT 1 COMMENT '我能不能收到别人的新消息通知',
  PRIMARY KEY (`user_id`, `contact_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for group_users
-- ----------------------------
DROP TABLE IF EXISTS `group_users`;
CREATE TABLE `group_users`  (
  `group_id` int NOT NULL,
  `user_id` int NOT NULL,
  `notify` int NOT NULL DEFAULT 1,
  PRIMARY KEY (`group_id`, `user_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for groups
-- ----------------------------
DROP TABLE IF EXISTS `groups`;
CREATE TABLE `groups`  (
  `group_id` int NOT NULL COMMENT '群组id',
  `group_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '群组名称',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上次信息更新的时间(群组本身的信息或群组成员的信息)',
  PRIMARY KEY (`group_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for messages
-- ----------------------------
DROP TABLE IF EXISTS `messages`;
CREATE TABLE `messages`  (
  `from_user_id` int NOT NULL COMMENT '发消息的用户id',
  `to_id` int NOT NULL COMMENT '收消息的id，根据is_group决定是用户还是群组',
  `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '消息到达服务器的时间',
  `text` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT '' COMMENT '消息内容',
  `type` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'text' COMMENT '消息类型(text, image, gif, file)',
  `is_group` int NOT NULL DEFAULT 0 COMMENT 'to_id是群组还是用户'
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users`  (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `user_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `salt` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '盐',
  `auth_string` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '认证字符串',
  `last_login` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上次下线的时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上次用户信息更新的时间',
  PRIMARY KEY (`user_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 44248194 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Procedure structure for insert_contact
-- ----------------------------
DROP PROCEDURE IF EXISTS `insert_contact`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `insert_contact`(IN user_id1 INT, IN user_id2 INT)
BEGIN
	INSERT IGNORE INTO contacts(user_id, contact_id)
	VALUES (user_id1, user_id2);
	INSERT IGNORE INTO contacts(user_id, contact_id)
	VALUES (user_id2, user_id1);
END
;;
delimiter ;

-- ----------------------------
-- Procedure structure for insert_user
-- ----------------------------
DROP PROCEDURE IF EXISTS `insert_user`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `insert_user`(IN user_id INT,IN user_name VARCHAR(255))
BEGIN
	INSERT INTO users(user_id, user_name)
	VALUES (user_id, user_name);
END
;;
delimiter ;

-- ----------------------------
-- Procedure structure for login
-- ----------------------------
DROP PROCEDURE IF EXISTS `login`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `login`(IN _user_id INT, IN _user_name VARCHAR(255), IN _last_login DATETIME)
BEGIN
	DECLARE old_user_name VARCHAR(255);

	SELECT user_name INTO old_user_name
	FROM users
	WHERE users.user_id = _user_id;

	IF old_user_name IS NOT NULL THEN
		IF old_user_name = _user_name THEN  -- 用户信息没有发生变化，只需要更新last_login
			UPDATE users
			SET users.last_login = _last_login
			WHERE users.user_id = _user_id;
		ELSE  -- 用户信息发生变化，更新除id外所有列
			UPDATE users
			SET users.user_name = _user_name,
					users.update_time = CURRENT_TIMESTAMP,
					users.last_login = _last_login
			WHERE users.user_id = _user_id;
		END IF;
	ELSE
		CALL insert_user(_user_id, _user_name);
	END IF;
END
;;
delimiter ;

-- ----------------------------
-- Procedure structure for query_user
-- ----------------------------
DROP PROCEDURE IF EXISTS `query_user`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `query_user`(IN _user_id INT)
BEGIN
	SELECT user_name
	FROM users
	WHERE user_id = _user_id;
END
;;
delimiter ;

SET FOREIGN_KEY_CHECKS = 1;
