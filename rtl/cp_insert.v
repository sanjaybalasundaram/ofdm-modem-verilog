// Cyclic prefix insertion: store one 64-sample symbol, then send
// samples 48..63 (the prefix) followed by samples 0..63  -> 80 samples.
module cp_insert (
    input                    clk,
    input                    rst_n,
    input                    in_valid,
    input      signed [15:0] in_re,
    input      signed [15:0] in_im,
    output                   in_ready,
    output reg               out_valid,
    output reg signed [15:0] out_re,
    output reg signed [15:0] out_im
);
    localparam N = 64, CP = 16;
    localparam FILL = 1'b0, SEND = 1'b1;

    reg signed [15:0] buf_re [0:N-1];
    reg signed [15:0] buf_im [0:N-1];
    reg       state;
    reg [6:0] cnt;

    assign in_ready = (state == FILL);
    wire [5:0] rd = (cnt < CP) ? (N - CP + cnt) : (cnt - CP);

    always @(posedge clk) begin
        if (!rst_n) begin
            state     <= FILL;
            cnt       <= 7'd0;
            out_valid <= 1'b0;
            out_re    <= 16'sd0;
            out_im    <= 16'sd0;
        end else if (state == FILL) begin
            out_valid <= 1'b0;
            if (in_valid) begin
                buf_re[cnt[5:0]] <= in_re;
                buf_im[cnt[5:0]] <= in_im;
                cnt <= (cnt == N - 1) ? 7'd0 : cnt + 7'd1;
                if (cnt == N - 1) state <= SEND;
            end
        end else begin
            out_valid <= 1'b1;
            out_re    <= buf_re[rd];
            out_im    <= buf_im[rd];
            cnt <= (cnt == N + CP - 1) ? 7'd0 : cnt + 7'd1;
            if (cnt == N + CP - 1) state <= FILL;
        end
    end
endmodule
