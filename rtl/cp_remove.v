// Cyclic prefix removal: of every 80 incoming samples, drop the first 16.
module cp_remove (
    input                    clk,
    input                    rst_n,
    input                    in_valid,
    input      signed [15:0] in_re,
    input      signed [15:0] in_im,
    output reg               out_valid,
    output reg signed [15:0] out_re,
    output reg signed [15:0] out_im
);
    localparam N = 64, CP = 16;
    reg [6:0] cnt;

    always @(posedge clk) begin
        if (!rst_n) begin
            cnt       <= 7'd0;
            out_valid <= 1'b0;
            out_re    <= 16'sd0;
            out_im    <= 16'sd0;
        end else begin
            out_valid <= in_valid && (cnt >= CP);
            if (in_valid) begin
                out_re <= in_re;
                out_im <= in_im;
                cnt <= (cnt == N + CP - 1) ? 7'd0 : cnt + 7'd1;
            end
        end
    end
endmodule
