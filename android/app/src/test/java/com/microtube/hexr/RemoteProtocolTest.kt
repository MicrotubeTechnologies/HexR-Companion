package com.microtube.hexr

import com.microtube.hexr.remote.Message
import com.microtube.hexr.remote.NearbyGlove
import com.microtube.hexr.remote.RemoteProtocol
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Headsets tab's side of HexR Remote, against the same reference lines as the package's
 * `Tests/Editor/RemoteTests.cs`.
 *
 * Same reason as [ProtocolTest]: one wire format, two languages. The request strings below are
 * exactly what the C# suite parses, and the status line is exactly what it produces, so if the
 * two sides ever disagree about the protocol one of the two suites goes red.
 */
class RemoteProtocolTest {

    // -- requests: byte-for-byte what RemoteTests.cs parses ------------------

    @Test
    fun requests_matchTheHeadsetsReferenceLines() {
        assertEquals("""{"type":"glove","action":"connect","hand":"left"}""", RemoteProtocol.glove("connect", "Left"))
        assertEquals("""{"type":"glove","action":"disconnect","hand":"right"}""", RemoteProtocol.glove("disconnect", "Right"))
        assertEquals("""{"type":"release"}""", RemoteProtocol.release())
        assertEquals("""{"type":"scene","index":2}""", RemoteProtocol.scene(2))
        assertEquals("""{"type":"command","id":"reset"}""", RemoteProtocol.command("reset"))
        assertEquals("""{"type":"stream","action":"start"}""", RemoteProtocol.stream("start"))
        assertEquals("""{"type":"hello","protocol":1,"client":"HexR Tester"}""", RemoteProtocol.hello("HexR Tester"))
    }

    @Test
    fun strings_areEscaped() {
        assertEquals("\"a\\\"b\\\\c\\n\"", RemoteProtocol.str("a\"b\\c\n"))
    }

    // -- status: exactly what RemoteTests.cs produces -------------------------

    private val referenceStatus =
        """{"type":"status","protocol":1,"id":"q3-1","name":"Quest 3","model":"Oculus Quest 3",""" +
            """"platform":"quest","app":"HexR Demo","appVersion":"1.2","hexrVersion":"0.10.0",""" +
            """"paused":false,"headsetBatteryPct":71,""" +
            """"scene":{"index":1,"name":"Hospital Tutorial"},""" +
            """"scenes":[{"index":0,"name":"Basic Tutorial"},{"index":1,"name":"Hospital Tutorial"}],""" +
            """"gloves":[{"hand":"left","state":"connected","message":"Connected","batteryPct":83,"pressureDeciKPa":[10,0,0,0,0,0,452]},""" +
            """{"hand":"right","state":"disconnected","message":"","batteryPct":-1,"pressureDeciKPa":[]}],""" +
            """"stream":{"state":"live","port":47802,"width":1024,"height":1024,"viewers":1,"message":""},""" +
            """"commands":[{"id":"reset","label":"Reset demo"}],""" +
            """"allowGloveControl":true,"allowVideo":true,"exposeScenes":true,"controllers":2}"""

    @Test
    fun status_readsEveryField() {
        val msg = RemoteProtocol.parseLine(referenceStatus)
        assertTrue(msg is Message.Status)
        val s = (msg as Message.Status).status

        assertEquals("q3-1", s.id)
        assertEquals("HexR Demo", s.app)
        assertEquals("quest", s.platform)
        assertEquals(71, s.headsetBatteryPct)
        assertEquals("Hospital Tutorial", s.scene.name)
        assertEquals(2, s.scenes.size)
        assertTrue(s.exposeScenes)
        assertEquals(2, s.controllers)

        val left = s.glove("Left")!!
        assertTrue(left.connected)
        assertEquals(83, left.batteryPct)
        assertEquals(1.0, left.kpa(0)!!, 1e-9)
        assertEquals(45.2, left.kpa(6)!!, 1e-9)

        val right = s.glove("right")!!
        assertFalse(right.connected)
        assertEquals(-1, right.batteryPct)
        assertNull(right.kpa(0))

        assertTrue(s.stream.live)
        assertEquals(47802, s.stream.port)
        assertEquals(1024, s.stream.width)
        assertEquals("Reset demo", s.commands.single().label)
    }

    @Test
    fun errorsAndWelcome_areRecognised() {
        val err = RemoteProtocol.parseLine("""{"type":"error","request":"command","message":"This app has no command \"nope\"."}""")
        assertEquals(Message.Error("command", "This app has no command \"nope\"."), err)

        val hello = RemoteProtocol.parseLine("""{"type":"hello","protocol":1,"id":"q3-1","control":47801,"video":47802}""")
        assertEquals(Message.Welcome("q3-1", 47801, 47802), hello)

        assertEquals(Message.Other, RemoteProtocol.parseLine("not json"))
    }

    @Test
    fun announce_isReadAndAnythingElseIsIgnored() {
        val a = RemoteProtocol.parseAnnounce(
            """{"hexr":1,"type":"announce","id":"q3-1","name":"Quest 3","model":"Oculus Quest 3","platform":"quest",""" +
                """"app":"HexR Demo","appId":"com.microtube.demo","hexrVersion":"0.10.0","control":47801,"video":47802,"startedAt":1791966541289}""",
        )!!
        assertEquals("q3-1", a.id)
        assertEquals(47801, a.control)
        assertEquals(1791966541289L, a.startedAt)

        assertNull(RemoteProtocol.parseAnnounce("""{"type":"status","id":"q3-1"}"""))
        assertNull(RemoteProtocol.parseAnnounce("garbage"))
    }

    @Test
    fun addressTypedIn_takesAPortOrTheControlPort() {
        assertEquals("192.168.1.20" to RemoteProtocol.CONTROL_PORT, RemoteProtocol.parseAddress(" 192.168.1.20 "))
        assertEquals("10.0.2.2" to 47811, RemoteProtocol.parseAddress("10.0.2.2:47811"))
        assertEquals("quest-3.local" to RemoteProtocol.CONTROL_PORT, RemoteProtocol.parseAddress("quest-3.local"))
        assertNull(RemoteProtocol.parseAddress(""))
        assertNull(RemoteProtocol.parseAddress("10.0.2.2:"))
        assertNull(RemoteProtocol.parseAddress("10.0.2.2:99999"))
        assertNull(RemoteProtocol.parseAddress("http://10.0.2.2"))
        assertNull(RemoteProtocol.parseAddress("a b"))
    }

    // -- video framing: the bytes VideoServer.java writes ---------------------

    private fun bytes(hex: String) = hex.split(" ").map { it.toInt(16).toByte() }.toByteArray()

    @Test
    fun videoHeader_isHXV1_widthHeightCodec_bigEndian() {
        val h = RemoteProtocol.parseVideoHeader(bytes("48 58 56 31 04 00 04 00 01"))!!
        assertEquals(1024, h.width)
        assertEquals(1024, h.height)
        assertEquals(RemoteProtocol.CODEC_H264, h.codec)

        assertNull(RemoteProtocol.parseVideoHeader(bytes("48 58 56 32 04 00 04 00 01")))
    }

    @Test
    fun packetHeader_isLengthFlagsPts_bigEndian() {
        val p = RemoteProtocol.parsePacketHeader(bytes("00 00 00 04 02 00 00 00 00 00 00 03 e8"))
        assertEquals(4, p.length)
        assertTrue(p.key)
        assertFalse(p.config)
        assertEquals(1000L, p.ptsUs)

        val big = RemoteProtocol.parsePacketHeader(bytes("00 01 00 00 01 00 00 00 00 00 00 00 00"))
        assertEquals(65536, big.length)
        assertTrue(big.config)
    }

    // -- picking a glove, and trigger all (HexR 0.10.6) --------------------------

    @Test
    fun gloveRequests_matchTheReferenceLines() {
        assertEquals("""{"type":"glove","action":"search"}""", RemoteProtocol.gloveSearch())
        assertEquals(
            """{"type":"glove","action":"connect","hand":"left","address":"D4:3D:39:A1:B2:C3"}""",
            RemoteProtocol.connectGloveAt("Left", "D4:3D:39:A1:B2:C3"),
        )
        assertEquals("""{"type":"glove","action":"forget","hand":"left"}""", RemoteProtocol.glove("forget", "left"))
        assertEquals("""{"type":"trigger"}""", RemoteProtocol.trigger())
    }

    @Test
    fun status_readsTheSavedGlovesAndTheLastSearch() {
        val line = referenceStatus.dropLast(1).replace(
            """"pressureDeciKPa":[10,0,0,0,0,0,452]}""",
            """"pressureDeciKPa":[10,0,0,0,0,0,452],"savedAddress":"D4:3D:39:A1:B2:C3"}""",
        ) + ""","gloveSearch":{"state":"done","message":"","found":[""" +
            """{"address":"D4:3D:39:D4:E5:F6","name":"HaptGloveAR Right","hand":"right","rssi":-48},""" +
            """{"address":"","name":"x"},{"address":"AA:BB","name":"HexR 07","hand":"up","rssi":"near"}]}}"""
        val s = (RemoteProtocol.parseLine(line) as Message.Status).status
        assertEquals("D4:3D:39:A1:B2:C3", s.glove("left")!!.savedAddress)
        assertEquals("", s.glove("right")!!.savedAddress)
        assertEquals("done", s.gloveSearch!!.state)
        assertEquals(
            listOf(
                NearbyGlove("D4:3D:39:D4:E5:F6", "HaptGloveAR Right", "right", -48),
                NearbyGlove("AA:BB", "HexR 07", "", 0),
            ),
            s.gloveSearch!!.found,
        )
    }

    @Test
    fun status_fromAHeadsetBefore0106_cannotSearch() {
        val s = (RemoteProtocol.parseLine(referenceStatus) as Message.Status).status
        assertNull(s.gloveSearch)
    }
}
