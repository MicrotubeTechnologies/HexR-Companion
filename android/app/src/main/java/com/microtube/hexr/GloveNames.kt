package com.microtube.hexr

import android.content.Context

/**
 * A name for every glove, worked out from its Bluetooth address alone.
 *
 * Every left glove advertises the same name, and so does every right one, so the only thing that
 * tells two arm modules apart is the address, which nobody can remember. This turns the address
 * into an adjective, an animal and a number ("Amber Otter 4"), the same way everywhere: any HEXR
 * Companion, phone or computer, names the same glove the same, with nothing shared between them
 * and nothing to set up. A name someone types in still wins, on that device.
 *
 * The recipe, which the desktop's hexr/glovenames.py follows exactly:
 *  1. the address's hex digits, upper case, nothing else ("D4:3D:39:A1:B2:C3" -> "D43D39A1B2C3");
 *  2. their FNV-1a 32-bit hash (offset basis 2166136261, prime 16777619, over the ASCII bytes);
 *  3. adjective = ADJECTIVES[hash % 64], animal = ANIMALS[(hash >> 6) % 64],
 *     number = (hash >> 12) % 10 + 1;
 *  4. "Adjective Animal N" in English, 形容词动物N号 in Chinese. 40960 names.
 * The lists are part of the recipe: never reorder or change an entry, or every glove gets a new
 * name. GloveNamesTest holds the reference names both apps are tested against.
 */
object GloveNames {
    /** (English, Chinese), in this order for good. */
    val ADJECTIVES = listOf(
        "Amber" to "琥珀", "Azure" to "蔚蓝", "Bold" to "大胆", "Brave" to "勇敢",
        "Bright" to "明亮", "Brisk" to "轻快", "Calm" to "沉静", "Clever" to "聪明",
        "Coral" to "珊瑚", "Cosmic" to "星际", "Crimson" to "深红", "Daring" to "无畏",
        "Dusky" to "暮色", "Eager" to "热切", "Fiery" to "火焰", "Frosty" to "霜白",
        "Gentle" to "温和", "Golden" to "金色", "Happy" to "快乐", "Hazel" to "榛色",
        "Honest" to "诚实", "Indigo" to "靛蓝", "Ivory" to "象牙", "Jade" to "翡翠",
        "Jolly" to "欢乐", "Keen" to "敏锐", "Kind" to "善良", "Lively" to "活泼",
        "Lucky" to "幸运", "Lunar" to "月光", "Merry" to "愉快", "Mighty" to "强大",
        "Misty" to "薄雾", "Noble" to "高贵", "Olive" to "橄榄", "Plucky" to "机灵",
        "Polar" to "极地", "Proud" to "骄傲", "Quick" to "敏捷", "Quiet" to "安静",
        "Rapid" to "迅疾", "Royal" to "皇家", "Ruby" to "红宝石", "Rusty" to "锈色",
        "Sandy" to "沙色", "Scarlet" to "猩红", "Silver" to "银色", "Snowy" to "雪白",
        "Solar" to "太阳", "Spry" to "矫健", "Steady" to "稳健", "Stormy" to "风暴",
        "Sunny" to "阳光", "Swift" to "飞速", "Teal" to "青色", "Tidy" to "整洁",
        "Velvet" to "丝绒", "Vivid" to "鲜艳", "Witty" to "风趣", "Wild" to "狂野",
        "Windy" to "疾风", "Zesty" to "热情", "Cheery" to "开朗", "Sleek" to "流线",
    )

    val ANIMALS = listOf(
        "Otter" to "水獭", "Falcon" to "猎鹰", "Panda" to "熊猫", "Tiger" to "老虎",
        "Koala" to "考拉", "Lynx" to "猞猁", "Heron" to "苍鹭", "Bison" to "野牛",
        "Badger" to "獾", "Beaver" to "河狸", "Camel" to "骆驼", "Cobra" to "眼镜蛇",
        "Crane" to "仙鹤", "Dingo" to "澳洲野犬", "Dolphin" to "海豚", "Eagle" to "雄鹰",
        "Ferret" to "雪貂", "Finch" to "雀鸟", "Fox" to "狐狸", "Gecko" to "壁虎",
        "Gibbon" to "长臂猿", "Hare" to "野兔", "Hawk" to "鹰", "Hedgehog" to "刺猬",
        "Ibis" to "朱鹭", "Jaguar" to "美洲豹", "Kestrel" to "红隼", "Kiwi" to "几维鸟",
        "Lemur" to "狐猴", "Leopard" to "花豹", "Lion" to "狮子", "Llama" to "羊驼",
        "Magpie" to "喜鹊", "Marten" to "貂", "Moose" to "驼鹿", "Narwhal" to "独角鲸",
        "Newt" to "蝾螈", "Ocelot" to "豹猫", "Orca" to "虎鲸", "Osprey" to "鱼鹰",
        "Owl" to "猫头鹰", "Panther" to "黑豹", "Parrot" to "鹦鹉", "Pelican" to "鹈鹕",
        "Penguin" to "企鹅", "Puffin" to "海鹦", "Puma" to "美洲狮", "Quail" to "鹌鹑",
        "Rabbit" to "兔子", "Raven" to "渡鸦", "Robin" to "知更鸟", "Salmon" to "鲑鱼",
        "Seal" to "海豹", "Shark" to "鲨鱼", "Sparrow" to "麻雀", "Squirrel" to "松鼠",
        "Swan" to "天鹅", "Tapir" to "貘", "Toucan" to "巨嘴鸟", "Turtle" to "海龟",
        "Walrus" to "海象", "Whale" to "鲸鱼", "Wolf" to "狼", "Yak" to "牦牛",
    )

    private fun hash(address: String): Long {
        var h = 2166136261L
        for (c in address.uppercase()) {
            if (c !in '0'..'9' && c !in 'A'..'F') continue
            h = ((h xor c.code.toLong()) * 16777619L) and 0xFFFFFFFFL
        }
        return h
    }

    /**
     * What this phone calls the glove at this address: a name given to it on the Headsets tab, or
     * else its own, in the app's language.
     */
    fun nameFor(context: Context, address: String): String =
        context.getSharedPreferences("headsets", Context.MODE_PRIVATE).getString("glove:${address.uppercase()}", null)
            ?: autoName(address, chinese = I18n.language == I18n.ZH_CN)

    /** The glove's own name, from its address: "Amber Otter 4", or "琥珀水獭4号" in Chinese. */
    fun autoName(address: String, chinese: Boolean = false): String {
        val h = hash(address)
        val adjective = ADJECTIVES[(h % 64).toInt()]
        val animal = ANIMALS[((h shr 6) % 64).toInt()]
        val number = (h shr 12) % 10 + 1
        return if (chinese) "${adjective.second}${animal.second}${number}号" else "${adjective.first} ${animal.first} $number"
    }
}
