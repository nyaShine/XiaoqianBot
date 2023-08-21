SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for authenticated_guilds
-- ----------------------------
CREATE TABLE `authenticated_guilds`  (
  `authenticated_guild_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `guild_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  PRIMARY KEY (`authenticated_guild_id`) USING BTREE,
  UNIQUE INDEX `guild_id_UNIQUE`(`guild_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 4 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for email_addresses
-- ----------------------------
CREATE TABLE `email_addresses`  (
  `email_address_id` int(11) NOT NULL AUTO_INCREMENT,
  `email_address` varchar(255) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `guild_id` varchar(50) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `user_id` varchar(50) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  PRIMARY KEY (`email_address_id`) USING BTREE,
  UNIQUE INDEX `email_address_guild_id`(`email_address`, `guild_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 5 CHARACTER SET = utf8 COLLATE = utf8_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for email_domains
-- ----------------------------
CREATE TABLE `email_domains`  (
  `email_domain_id` int(11) NOT NULL AUTO_INCREMENT,
  `email_domain` varchar(255) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `guild_id` varchar(50) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `guild_domain_id` varchar(255) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  PRIMARY KEY (`email_domain_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 15 CHARACTER SET = utf8 COLLATE = utf8_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for email_verification_roles
-- ----------------------------
CREATE TABLE `email_verification_roles`  (
  `email_verification_role_id` int(11) NOT NULL AUTO_INCREMENT,
  `role` varchar(50) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `guild_id` varchar(50) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  PRIMARY KEY (`email_verification_role_id`) USING BTREE,
  UNIQUE INDEX `guild_id`(`guild_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8 COLLATE = utf8_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for management_roles
-- ----------------------------
CREATE TABLE `management_roles`  (
  `management_roles_id` int(11) NOT NULL AUTO_INCREMENT,
  `role` varchar(20) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `guild_id` varchar(50) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `role_type` varchar(50) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  PRIMARY KEY (`management_roles_id`) USING BTREE,
  UNIQUE INDEX `role`(`role`, `guild_id`, `role_type`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 27 CHARACTER SET = utf8 COLLATE = utf8_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for minecraft_servers
-- ----------------------------
CREATE TABLE `minecraft_servers`  (
  `server_address` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `server_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `server_description` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `guild_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`server_address`, `guild_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for question_answer
-- ----------------------------
CREATE TABLE `question_answer`  (
  `question_answer_id` int(11) NOT NULL AUTO_INCREMENT,
  `question` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `answer` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL,
  `guild_id` varchar(50) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `guild_question_id` int(11) NOT NULL,
  PRIMARY KEY (`question_answer_id`) USING BTREE,
  INDEX `idx_guild`(`guild_id`, `guild_question_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 286 CHARACTER SET = utf8 COLLATE = utf8_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for question_answer_error_messages
-- ----------------------------
CREATE TABLE `question_answer_error_messages`  (
  `question_answer_error_messages_id` int(11) NOT NULL AUTO_INCREMENT,
  `question_answer_id` int(11) NOT NULL,
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL,
  PRIMARY KEY (`question_answer_error_messages_id`) USING BTREE,
  UNIQUE INDEX `idx_unique_error`(`question_answer_id`, `error_message`(500)) USING BTREE,
  INDEX `idx_question_answer_id`(`question_answer_id`) USING BTREE,
  CONSTRAINT `question_answer_error_messages_ibfk_1` FOREIGN KEY (`question_answer_id`) REFERENCES `question_answer` (`question_answer_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for question_answer_image
-- ----------------------------
CREATE TABLE `question_answer_image`  (
  `image_id` int(11) NOT NULL AUTO_INCREMENT,
  `question_answer_id` int(11) NOT NULL,
  `image_seq` int(11) NOT NULL,
  PRIMARY KEY (`image_id`) USING BTREE,
  INDEX `question_answer_id`(`question_answer_id`) USING BTREE,
  CONSTRAINT `question_answer_image_ibfk_1` FOREIGN KEY (`question_answer_id`) REFERENCES `question_answer` (`question_answer_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 31 CHARACTER SET = utf8 COLLATE = utf8_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for question_answer_watermark
-- ----------------------------
CREATE TABLE `question_answer_watermark`  (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` varchar(50) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `watermark` varchar(15) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `is_dense` tinyint(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `idx_guild_id`(`guild_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 9 CHARACTER SET = utf8 COLLATE = utf8_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for rss_feed
-- ----------------------------
CREATE TABLE `rss_feed`  (
  `rss_feed_id` int(11) NOT NULL AUTO_INCREMENT,
  `url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `system_min_interval` int(11) NOT NULL DEFAULT 30,
  `block_duration` int(11) NOT NULL DEFAULT 0,
  `block_count` int(11) NOT NULL DEFAULT 0,
  `current_interval` int(11) NOT NULL DEFAULT 30,
  `last_updated` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_blocked` timestamp NULL DEFAULT NULL,
  `block_level` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`rss_feed_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 12 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for rss_item
-- ----------------------------
CREATE TABLE `rss_item`  (
  `rss_item_id` int(11) NOT NULL AUTO_INCREMENT,
  `rss_feed_id` int(11) NOT NULL,
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `link` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `published_date` datetime NULL DEFAULT NULL,
  PRIMARY KEY (`rss_item_id`) USING BTREE,
  INDEX `rss_feed_id`(`rss_feed_id`) USING BTREE,
  CONSTRAINT `rss_item_ibfk_1` FOREIGN KEY (`rss_feed_id`) REFERENCES `rss_feed` (`rss_feed_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 200 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for rss_item_delivery
-- ----------------------------
CREATE TABLE `rss_item_delivery`  (
  `rss_item_delivery_id` int(11) NOT NULL AUTO_INCREMENT,
  `rss_item_id` int(11) NOT NULL,
  `guild_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `channel_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  PRIMARY KEY (`rss_item_delivery_id`) USING BTREE,
  INDEX `rss_item_id`(`rss_item_id`) USING BTREE,
  CONSTRAINT `rss_item_delivery_ibfk_1` FOREIGN KEY (`rss_item_id`) REFERENCES `rss_item` (`rss_item_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 68 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for rss_subscription
-- ----------------------------
CREATE TABLE `rss_subscription`  (
  `rss_subscription_id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_rss_subscription_id` int(11) NOT NULL,
  `guild_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `channel_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `rss_feed_id` int(11) NOT NULL,
  `custom_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `user_min_interval` int(11) NOT NULL,
  `max_age` int(11) NOT NULL DEFAULT 90 COMMENT 'Max age in days for an RSS item to be sent',
  PRIMARY KEY (`rss_subscription_id`) USING BTREE,
  UNIQUE INDEX `guild_channel_feed`(`guild_id`, `channel_id`, `rss_feed_id`) USING BTREE,
  INDEX `rss_feed_id`(`rss_feed_id`) USING BTREE,
  CONSTRAINT `rss_subscription_ibfk_1` FOREIGN KEY (`rss_feed_id`) REFERENCES `rss_feed` (`rss_feed_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 20 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Triggers structure for table rss_feed
-- ----------------------------
DROP TRIGGER IF EXISTS `update_subscription_interval`;
delimiter ;;
CREATE TRIGGER `update_subscription_interval` AFTER UPDATE ON `rss_feed` FOR EACH ROW BEGIN
   IF OLD.system_min_interval <> NEW.system_min_interval THEN
      UPDATE `rss_subscription` SET user_min_interval = NEW.system_min_interval
      WHERE rss_feed_id = NEW.rss_feed_id AND user_min_interval < NEW.system_min_interval;
   END IF;
END
;;
delimiter ;

-- ----------------------------
-- Triggers structure for table rss_subscription
-- ----------------------------
DROP TRIGGER IF EXISTS `update_rss_feed_interval`;
delimiter ;;
CREATE TRIGGER `update_rss_feed_interval` AFTER UPDATE ON `rss_subscription` FOR EACH ROW BEGIN
   IF OLD.user_min_interval <> NEW.user_min_interval THEN
      UPDATE `rss_feed` SET current_interval = 
      (SELECT MIN(user_min_interval) FROM `rss_subscription` WHERE rss_feed_id = NEW.rss_feed_id)
      WHERE rss_feed_id = NEW.rss_feed_id;
   END IF;
END
;;
delimiter ;

-- ----------------------------
-- Triggers structure for table rss_subscription
-- ----------------------------
DROP TRIGGER IF EXISTS `update_rss_feed_interval_on_update`;
delimiter ;;
CREATE TRIGGER `update_rss_feed_interval_on_update` AFTER UPDATE ON `rss_subscription` FOR EACH ROW BEGIN
   IF OLD.user_min_interval <> NEW.user_min_interval THEN
      UPDATE `rss_feed` SET current_interval = 
      (SELECT MIN(user_min_interval) FROM `rss_subscription` WHERE rss_feed_id = NEW.rss_feed_id)
      WHERE rss_feed_id = NEW.rss_feed_id;
   END IF;
END
;;
delimiter ;

SET FOREIGN_KEY_CHECKS = 1;
