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

 Date: 30/11/2024 22:41:14
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for contacts
-- ----------------------------
DROP TABLE IF EXISTS `contacts`;
CREATE TABLE `contacts` (
  `user_id` int NOT NULL COMMENT '我',
  `contact_id` int NOT NULL COMMENT '别人',
  `notify` int NOT NULL DEFAULT '1' COMMENT '我能不能收到别人的新消息通知',
  PRIMARY KEY (`user_id`,`contact_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for files
-- ----------------------------
DROP TABLE IF EXISTS `files`;
CREATE TABLE `files` (
  `file_hash` varchar(128) NOT NULL COMMENT '文件的SHA512哈希值',
  `file_suffix` varchar(128) DEFAULT NULL COMMENT '文件的后缀名，可为空',
  PRIMARY KEY (`file_hash`),
  UNIQUE KEY `file_hash_idx` (`file_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for group_users
-- ----------------------------
DROP TABLE IF EXISTS `group_users`;
CREATE TABLE `group_users` (
  `group_id` int NOT NULL,
  `user_id` int NOT NULL,
  `notify` int NOT NULL DEFAULT '1',
  PRIMARY KEY (`group_id`,`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for groups
-- ----------------------------
DROP TABLE IF EXISTS `groups`;
CREATE TABLE `groups` (
  `group_id` int NOT NULL COMMENT '群组id',
  `group_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '群组名称',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上次信息更新的时间(群组本身的信息或群组成员的信息)',
  PRIMARY KEY (`group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for messages
-- ----------------------------
DROP TABLE IF EXISTS `messages`;
CREATE TABLE `messages` (
  `from_user_id` int NOT NULL COMMENT '发消息的用户id',
  `to_id` int NOT NULL COMMENT '收消息的id，根据is_group决定是用户还是群组',
  `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '消息到达服务器的时间',
  `text` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT '' COMMENT '消息内容',
  `type` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'text' COMMENT '消息类型(text, image, gif, file)',
  `is_group` int NOT NULL DEFAULT '0' COMMENT 'to_id是群组还是用户'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for user_apn_tokens
-- ----------------------------
DROP TABLE IF EXISTS `user_apn_tokens`;
CREATE TABLE `user_apn_tokens` (
  `user_id` int NOT NULL COMMENT '用户ID',
  `user_apn_token` varchar(255) NOT NULL COMMENT '苹果设备的APN Token',
  PRIMARY KEY (`user_id`,`user_apn_token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `user_name` varchar(255) NOT NULL,
  `salt` varchar(255) DEFAULT NULL COMMENT '盐',
  `auth_string` varchar(255) DEFAULT NULL COMMENT '认证字符串',
  `last_login` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上次下线的时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上次用户信息更新的时间',
  PRIMARY KEY (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1506348631 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Procedure structure for init
-- ----------------------------
DROP PROCEDURE IF EXISTS `init`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `init`()
BEGIN
	INSERT IGNORE INTO users(user_id, user_name)
	VALUES(-1, 'Warning');
	
	INSERT IGNORE INTO users(user_id, user_name)
	VALUES(0, 'Server');
	
	INSERT IGNORE INTO `groups`(group_id, group_name)
	VALUES(-1, 'Broadcast');
END
;;
delimiter ;

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
-- Procedure structure for insert_file
-- ----------------------------
DROP PROCEDURE IF EXISTS `insert_file`;
delimiter ;;
CREATE DEFINER=`voltline`@`%` PROCEDURE `insert_file`(IN file_hash varchar(128), IN file_suffix varchar(128))
BEGIN
  INSERT INTO files VALUE(file_hash, file_suffix);
END
;;
delimiter ;

-- ----------------------------
-- Procedure structure for insert_group
-- ----------------------------
DROP PROCEDURE IF EXISTS `insert_group`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `insert_group`(IN _group_id INT, IN _group_name VARCHAR(255))
BEGIN
	INSERT INTO `groups`(group_id, group_name)
	VALUES(_group_id, _group_name);
END
;;
delimiter ;

-- ----------------------------
-- Procedure structure for insert_group_user
-- ----------------------------
DROP PROCEDURE IF EXISTS `insert_group_user`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `insert_group_user`(IN _group_id INT, IN _user_id INT)
BEGIN
	IF _group_id NOT IN (SELECT group_id FROM `groups`) THEN
		SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'group_id not in groups';
	END IF;
	
	IF _user_id NOT IN (SELECT user_id FROM users) THEN
		SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'user_id not in users';
	END IF;
	
	INSERT IGNORE INTO group_users(group_id, user_id)
	VALUES(_group_id, _user_id);
END
;;
delimiter ;

-- ----------------------------
-- Procedure structure for insert_message
-- ----------------------------
DROP PROCEDURE IF EXISTS `insert_message`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `insert_message`(
	IN _from INT, IN _to INT,
	IN _timestamp DATETIME,
	IN _text VARCHAR(1024), IN _type VARCHAR(10),
	IN _is_group INT
)
BEGIN
	IF _timestamp IS NULL THEN
		INSERT INTO messages(from_user_id, to_id, `text`, type, is_group)
		VALUES(_from, _to, _text, _type, _is_group);
	ELSE
		INSERT INTO messages(from_user_id, to_id, `text`, type, is_group, `timestamp`)
		VALUES(_from, _to, _text, _type, _is_group, _timestamp);
	END IF;
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
-- Procedure structure for insert_user_apn_token
-- ----------------------------
DROP PROCEDURE IF EXISTS `insert_user_apn_token`;
delimiter ;;
CREATE DEFINER=`voltline`@`%` PROCEDURE `insert_user_apn_token`(user_id int,  user_apn_token varchar(255))
BEGIN
	declare apn_token varchar(255) default '';
	select user_apn_token into apn_token
	from user_apn_tokens uat
	where user_id = uat.user_id
	and user_apn_token = uat.user_apn_token;
	IF apn_token = '' THEN
  insert into user_apn_tokens values(user_id, user_apn_token);
	END IF;
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
-- Procedure structure for query_file
-- ----------------------------
DROP PROCEDURE IF EXISTS `query_file`;
delimiter ;;
CREATE DEFINER=`voltline`@`%` PROCEDURE `query_file`(IN file_hash varchar(128), IN file_suffix varchar(128))
BEGIN
  SELECT file_hash
	FROM files f
	WHERE file_hash = f.file_hash
	AND file_suffix = f.file_suffix;
END
;;
delimiter ;

-- ----------------------------
-- Procedure structure for query_group
-- ----------------------------
DROP PROCEDURE IF EXISTS `query_group`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `query_group`(IN _group_id INT)
BEGIN
	SELECT group_name
	FROM `groups`
	WHERE group_id = _group_id;
END
;;
delimiter ;

-- ----------------------------
-- Procedure structure for query_group_user
-- ----------------------------
DROP PROCEDURE IF EXISTS `query_group_user`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `query_group_user`(IN _group_id INT)
BEGIN
	SELECT user_id
	FROM group_users
	WHERE group_id = _group_id;
END
;;
delimiter ;

-- ----------------------------
-- Procedure structure for query_sync_message
-- ----------------------------
DROP PROCEDURE IF EXISTS `query_sync_message`;
delimiter ;;
CREATE DEFINER=`lty`@`%` PROCEDURE `query_sync_message`(IN _id INT, IN _last_login DATETIME)
BEGIN
	CREATE TEMPORARY TABLE user_groups AS 
	SELECT group_id
	FROM group_users
	WHERE user_id = _id
	UNION
	SELECT -1 AS group_id;
	
	SELECT *
	FROM messages
	WHERE `timestamp` > _last_login
	AND (
		is_group = 0 AND (to_id = _id OR from_user_id = _id)
		OR
		is_group <> 0 AND to_id IN (SELECT * FROM user_groups)
	);
	
	DROP TEMPORARY TABLE user_groups;
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

-- ----------------------------
-- Procedure structure for query_user_apn_tokens
-- ----------------------------
DROP PROCEDURE IF EXISTS `query_user_apn_tokens`;
delimiter ;;
CREATE DEFINER=`voltline`@`%` PROCEDURE `query_user_apn_tokens`(user_id int)
BEGIN
  select user_apn_token
	from user_apn_tokens apn
	where user_id = apn.user_id;
END
;;
delimiter ;

SET FOREIGN_KEY_CHECKS = 1;
