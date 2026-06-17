package com.celestarc.furitrainer;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.world.phys.Vec3;
import org.lwjgl.glfw.GLFW;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public class FuriTrainerClient implements ClientModInitializer {
    private static final HttpClient HTTP_CLIENT = HttpClient.newHttpClient();
    private static final String SERVER_URL = "http://localhost:3000/teach";
    private static final String COGNITIVE_URL = "http://localhost:3000/teach-action";
    
    private int tickCounter = 0;
    private boolean isRecording = true;
    private boolean wasOPressed = false;
    private String currentlyUsingItem = null;

    @Override
    public void onInitializeClient() {
        // Event when breaking a block (Mining)
        PlayerBlockBreakEvents.AFTER.register((level, player, blockPos, state, blockEntity) -> {
            if (level.isClientSide() && isRecording) {
                String blockName = BuiltInRegistries.BLOCK.getKey(state.getBlock()).getPath();
                String toolName = "hand";
                if (!player.getMainHandItem().isEmpty()) {
                    toolName = BuiltInRegistries.ITEM.getKey(player.getMainHandItem().getItem()).getPath();
                }
                sendCognitiveDataAsync("break_block", blockName, toolName);
            }
        });

        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            if (client.player == null || client.level == null) return;

            long windowId = org.lwjgl.glfw.GLFW.glfwGetCurrentContext();
            boolean isOPressed = windowId != 0L && client.screen == null && GLFW.glfwGetKey(windowId, GLFW.GLFW_KEY_O) == GLFW.GLFW_PRESS;
            
            if (isOPressed && !wasOPressed) {
                isRecording = !isRecording;
                try {
                    client.player.sendSystemMessage(Component.literal("\u00A7e[Furi Trainer] \u00A7fRecording is now " + (isRecording ? "\u00A7aON" : "\u00A7cOFF")));
                } catch (Exception e) {}
            }
            wasOPressed = isOPressed;

            if (!isRecording) return; // Do not record if turned off

            // Event when using an item (Eating/Drinking/etc.)
            if (client.player.isUsingItem()) {
                if (currentlyUsingItem == null && !client.player.getUseItem().isEmpty()) {
                    currentlyUsingItem = BuiltInRegistries.ITEM.getKey(client.player.getUseItem().getItem()).getPath();
                }
            } else {
                if (currentlyUsingItem != null) {
                    sendCognitiveDataAsync("use_item", currentlyUsingItem, "");
                    currentlyUsingItem = null;
                }
            }

            tickCounter++;
            if (tickCounter % 2 != 0) return; // Run every 100ms

            boolean forward = client.options.keyUp.isDown();
            boolean back = client.options.keyDown.isDown();
            boolean left = client.options.keyLeft.isDown();
            boolean right = client.options.keyRight.isDown();
            boolean jump = client.options.keyJump.isDown();
            
            if (!forward && !back && !left && !right && !jump) {
                return;
            }

            String actionStr = "none";
            if (forward && jump) actionStr = "jump_forward";
            else if (forward) actionStr = "forward";
            else if (back) actionStr = "back";
            else if (left) actionStr = "left";
            else if (right) actionStr = "right";
            else if (jump) actionStr = "jump";

            // getLookAngle() is the Mojang mapping equivalent for getRotationVec(1.0F)
            Vec3 rotation = client.player.getLookAngle();
            Vec3 forwardDir = new Vec3(rotation.x, 0, rotation.z).normalize();
            
            BlockPos pos = client.player.blockPosition();
            BlockPos frontPos = pos.offset((int)Math.round(forwardDir.x), 0, (int)Math.round(forwardDir.z));
            
            boolean front1 = !client.level.getBlockState(frontPos).isAir();
            boolean front2 = !client.level.getBlockState(frontPos.above()).isAir();
            
            String frontType = "none";
            if (front1 && front2) frontType = "wall_2high";
            else if (front1) frontType = "wall_1high";

            boolean isAirBelow = client.level.getBlockState(pos.below()).isAir();
            boolean isStuck = client.player.horizontalCollision; 
            boolean inWater = client.player.isInWater();
            
            String targetDir = "front";
            if (back) targetDir = "back";
            else if (left) targetDir = "left";
            else if (right) targetDir = "right";
            String stateStr = String.format("%s_%s_stuck%b_airBelow%b_inWater%b", targetDir, frontType, isStuck, isAirBelow, inWater);

            sendDataAsync(stateStr, actionStr);
        });
    }

    private void sendDataAsync(String state, String action) {
        String json = String.format("{\"state\":\"%s\",\"action\":\"%s\"}", state, action);
        
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(SERVER_URL))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json))
                .build();

        HTTP_CLIENT.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .exceptionally(e -> null);
    }

    private void sendCognitiveDataAsync(String type, String target, String tool) {
        String json = String.format("{\"type\":\"%s\",\"target\":\"%s\",\"tool\":\"%s\"}", type, target, tool);
        
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(COGNITIVE_URL))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json))
                .build();

        HTTP_CLIENT.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .exceptionally(e -> null);
    }
}
